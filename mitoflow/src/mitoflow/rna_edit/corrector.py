"""RNA editing-based protein correction for plant mitochondrial genomes.

Takes predicted editing sites and applies them to correct CDS sequences,
then writes corrected GenBank and FASTA output.

Pipeline integration:
1. predictor.py predicts EditingSite objects
2. This module applies corrections in batch to GenBank files
3. Outputs: corrected GenBank, corrected protein/CDS FASTA, VCF, summary plots
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .predictor import EditingSite, correct_protein_with_editing

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GenBank correction
# ---------------------------------------------------------------------------

def correct_genbank_proteins(
    genbank_path: str | Path,
    editing_sites: list[EditingSite],
    output_path: str | Path,
) -> dict:
    """Apply RNA editing corrections to all CDS in a GenBank file.

    Reads the input GenBank, groups editing sites by gene, applies C-to-U
    corrections to each CDS, and writes a corrected GenBank file with
    updated translations and editing-site annotations.

    Args:
        genbank_path: Path to input GenBank file.
        editing_sites: List of EditingSite predictions.
        output_path: Path for corrected GenBank output.

    Returns:
        Dict with correction statistics:
        {
            "genes_corrected": int,
            "total_sites_applied": int,
            "corrections_per_gene": {gene: count},
        }
    """
    from Bio import SeqIO
    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord

    genbank_path = Path(genbank_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Group sites by gene
    sites_by_gene: dict[str, list[EditingSite]] = defaultdict(list)
    for site in editing_sites:
        sites_by_gene[site.gene].append(site)

    stats = {
        "genes_corrected": 0,
        "total_sites_applied": 0,
        "corrections_per_gene": {},
    }

    record = next(SeqIO.parse(str(genbank_path), "genbank"))

    for feat in record.features:
        if feat.type != "CDS":
            continue

        gene_name = _get_gene_name(feat)
        if not gene_name:
            continue

        # Try case-insensitive match
        gene_sites = sites_by_gene.get(gene_name)
        if gene_sites is None:
            gene_lower = gene_name.lower()
            for key, vals in sites_by_gene.items():
                if key.lower() == gene_lower:
                    gene_sites = vals
                    break
        if not gene_sites:
            continue

        # Extract original CDS
        cds_seq = str(feat.extract(record.seq)).upper()

        # Apply corrections to CDS
        corrected_cds = _apply_edits_to_cds(cds_seq, gene_sites)

        # Translate corrected CDS
        corrected_protein = correct_protein_with_editing(cds_seq, gene_sites)

        if not corrected_protein:
            logger.warning(
                "Correction produced empty protein for %s, skipping", gene_name
            )
            continue

        # Update the feature qualifiers
        feat.qualifiers["translation"] = [corrected_protein]
        feat.qualifiers["note"] = feat.qualifiers.get("note", [])
        if isinstance(feat.qualifiers["note"], str):
            feat.qualifiers["note"] = [feat.qualifiers["note"]]
        feat.qualifiers["note"].append(
            f"RNA editing: {len(gene_sites)} site(s) corrected"
        )

        # Record editing details
        edit_details = "; ".join(
            f"C→T@{s.position_cds}({s.original_aa}->{s.edited_aa})"
            for s in gene_sites
        )
        feat.qualifiers["rna_editing"] = [edit_details]

        stats["genes_corrected"] += 1
        stats["total_sites_applied"] += len(gene_sites)
        stats["corrections_per_gene"][gene_name] = len(gene_sites)

    # Add annotation history
    record.annotations["comment"] = (
        record.annotations.get("comment", "")
        + f"\nRNA editing corrections applied: {stats['total_sites_applied']} sites "
        f"in {stats['genes_corrected']} genes. "
        f"Date: {datetime.now().strftime('%Y-%m-%d')}"
    ).strip()

    SeqIO.write(record, str(output_path), "genbank")
    logger.info(
        "Wrote corrected GenBank: %s (%d genes, %d sites)",
        output_path, stats["genes_corrected"], stats["total_sites_applied"],
    )

    return stats


# ---------------------------------------------------------------------------
# FASTA output
# ---------------------------------------------------------------------------

def write_corrected_fasta(
    genbank_path: str | Path,
    editing_sites: list[EditingSite],
    output_dir: str | Path,
    name: str = "corrected",
) -> dict[str, Path]:
    """Write corrected protein FASTA and corrected CDS FASTA.

    Args:
        genbank_path: Path to input GenBank file.
        editing_sites: List of EditingSite predictions.
        output_dir: Directory for output files.
        name: Prefix for output file names.

    Returns:
        Dict with paths: {"protein": Path, "cds": Path}
    """
    from Bio import SeqIO

    genbank_path = Path(genbank_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group sites by gene
    sites_by_gene: dict[str, list[EditingSite]] = defaultdict(list)
    for site in editing_sites:
        sites_by_gene[site.gene].append(site)

    record = next(SeqIO.parse(str(genbank_path), "genbank"))

    protein_path = output_dir / f"{name}_proteins.fasta"
    cds_path = output_dir / f"{name}_cds.fasta"

    protein_records = []
    cds_records = []

    for feat in record.features:
        if feat.type != "CDS":
            continue

        gene_name = _get_gene_name(feat)
        if not gene_name:
            continue

        cds_seq = str(feat.extract(record.seq)).upper()

        # Find matching sites (case-insensitive)
        gene_sites = sites_by_gene.get(gene_name)
        if gene_sites is None:
            gene_lower = gene_name.lower()
            for key, vals in sites_by_gene.items():
                if key.lower() == gene_lower:
                    gene_sites = vals
                    break

        if gene_sites:
            # Corrected protein
            corrected_protein = correct_protein_with_editing(cds_seq, gene_sites)
            corrected_cds = _apply_edits_to_cds(cds_seq, gene_sites)
        else:
            # No edits -- use original
            corrected_protein = _translate(cds_seq)
            corrected_cds = cds_seq

        if not corrected_protein:
            continue

        # Protein record
        from Bio.Seq import Seq as SeqObj
        from Bio.SeqRecord import SeqRecord

        prot_rec = SeqRecord(
            SeqObj(corrected_protein),
            id=gene_name,
            description=_protein_description(gene_name, gene_sites),
        )
        protein_records.append(prot_rec)

        # CDS record
        cds_rec = SeqRecord(
            SeqObj(corrected_cds),
            id=gene_name,
            description=_cds_description(gene_name, gene_sites),
        )
        cds_records.append(cds_rec)

    with open(protein_path, "w") as f:
        SeqIO.write(protein_records, f, "fasta")

    with open(cds_path, "w") as f:
        SeqIO.write(cds_records, f, "fasta")

    logger.info(
        "Wrote corrected FASTA: %s (%d proteins), %s (%d CDS)",
        protein_path, len(protein_records),
        cds_path, len(cds_records),
    )

    return {"protein": protein_path, "cds": cds_path}


# ---------------------------------------------------------------------------
# VCF-like output
# ---------------------------------------------------------------------------

def generate_editing_vcf(
    editing_sites: list[EditingSite],
    genome_seq: str,
    output_path: str | Path,
) -> Path:
    """Write editing sites in VCF-like format.

    Produces a tab-delimited file with VCF-inspired columns for easy
    downstream analysis and visualization in genome browsers.

    Args:
        editing_sites: List of EditingSite predictions.
        genome_seq: Genome sequence (used for REF/ALT context).
        output_path: Output file path (.vcf or .tsv).

    Returns:
        Path to the generated file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    genome_seq = genome_seq.upper()

    header_lines = [
        "##fileformat=VCFv4.2",
        f"##fileDate={datetime.now().strftime('%Y%m%d')}",
        '##source=MitoFlow_RNAEditingCorrector',
        '##INFO=<ID=GENE,Number=1,Type=String,Description="Gene name">',
        '##INFO=<ID=CDS_POS,Number=1,Type=Integer,Description="1-based position in CDS">',
        '##INFO=<ID=CODON_POS,Number=1,Type=Integer,Description="Codon position (1-3)">',
        '##INFO=<ID=ORIG_CODON,Number=1,Type=String,Description="Original codon">',
        '##INFO=<ID=EDIT_CODON,Number=1,Type=String,Description="Edited codon">',
        '##INFO=<ID=ORIG_AA,Number=1,Type=String,Description="Original amino acid">',
        '##INFO=<ID=EDIT_AA,Number=1,Type=String,Description="Edited amino acid">',
        '##INFO=<ID=SYNONYMOUS,Number=0,Type=Flag,Description="Synonymous editing">',
        '##INFO=<ID=START_GAIN,Number=0,Type=Flag,Description="Start codon creation">',
        '##INFO=<ID=STOP_REMOVAL,Number=0,Type=Flag,Description="Stop codon removal">',
        '##INFO=<ID=CONFIDENCE,Number=1,Type=String,Description="Confidence level">',
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
    ]

    with open(output_path, "w") as f:
        for line in header_lines:
            f.write(line + "\n")

        for i, site in enumerate(sorted(editing_sites, key=lambda s: s.position_genome), 1):
            # REF and ALT bases
            pos = site.position_genome - 1  # 0-based
            if 0 <= pos < len(genome_seq):
                ref = genome_seq[pos]
            else:
                ref = "C"

            alt = "T" if ref == "C" else "T"

            # INFO field
            info_parts = [
                f"GENE={site.gene}",
                f"CDS_POS={site.position_cds}",
                f"CODON_POS={site.codon_position}",
                f"ORIG_CODON={site.original_codon}",
                f"EDIT_CODON={site.edited_codon}",
                f"ORIG_AA={site.original_aa}",
                f"EDIT_AA={site.edited_aa}",
                f"CONFIDENCE={site.confidence}",
            ]
            if site.is_synonymous:
                info_parts.append("SYNONYMOUS")
            if site.is_start_codon_creation:
                info_parts.append("START_GAIN")
            if site.is_stop_codon_removal:
                info_parts.append("STOP_REMOVAL")

            info_str = ";".join(info_parts)
            site_id = f"edit_{i:04d}"

            f.write(
                f"chrMT\t{site.position_genome}\t{site_id}\t{ref}\t{alt}"
                f"\t.\tPASS\t{info_str}\n"
            )

    logger.info("Wrote editing VCF: %s (%d sites)", output_path, len(editing_sites))
    return output_path


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

def plot_editing_summary(
    editing_sites: list[EditingSite],
    output_path: str | Path,
    dpi: int = 300,
) -> Path:
    """Create matplotlib visualization of editing summary.

    Produces a multi-panel figure:
    1. Bar chart: editing sites per gene
    2. Pie chart: synonymous vs nonsynonymous
    3. Bar chart: codon position distribution

    Args:
        editing_sites: List of EditingSite predictions.
        output_path: Output image path (PNG/PDF/SVG).
        dpi: Resolution for raster formats.

    Returns:
        Path to the saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not editing_sites:
        logger.warning("No editing sites to plot")
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No editing sites to display",
                ha="center", va="center", fontsize=14)
        fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return output_path

    # Compute statistics
    sites_by_gene: dict[str, int] = defaultdict(int)
    n_syn = 0
    n_nonsyn = 0
    n_start = 0
    n_stop = 0
    codon_counts = {1: 0, 2: 0, 3: 0}

    for site in editing_sites:
        sites_by_gene[site.gene] += 1
        if site.is_synonymous:
            n_syn += 1
        else:
            n_nonsyn += 1
        if site.is_start_codon_creation:
            n_start += 1
        if site.is_stop_codon_removal:
            n_stop += 1
        codon_counts[site.codon_position] = codon_counts.get(site.codon_position, 0) + 1

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(
        f"RNA Editing Summary ({len(editing_sites)} sites)",
        fontsize=14, fontweight="bold",
    )

    # Panel 1: Bar chart of editing per gene
    ax1 = axes[0]
    sorted_genes = sorted(sites_by_gene.items(), key=lambda x: -x[1])
    if sorted_genes:
        gene_names = [g for g, _ in sorted_genes]
        gene_counts = [c for _, c in sorted_genes]
        bar_colors = []
        for g in gene_names:
            gene_sites = [s for s in editing_sites if s.gene == g]
            if any(s.is_start_codon_creation for s in gene_sites):
                bar_colors.append("#e74c3c")
            elif any(s.is_stop_codon_removal for s in gene_sites):
                bar_colors.append("#3498db")
            else:
                bar_colors.append("#2ecc71")
        ax1.barh(range(len(gene_names)), gene_counts, color=bar_colors)
        ax1.set_yticks(range(len(gene_names)))
        ax1.set_yticklabels(gene_names, fontsize=8)
        ax1.set_xlabel("Number of editing sites")
        ax1.set_title("Editing sites per gene")
        ax1.invert_yaxis()
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#2ecc71", label="Standard"),
            Patch(facecolor="#e74c3c", label="Start codon gain"),
            Patch(facecolor="#3498db", label="Stop codon removal"),
        ]
        ax1.legend(handles=legend_elements, fontsize=7, loc="lower right")

    # Panel 2: Pie chart of synonymous vs nonsynonymous
    ax2 = axes[1]
    pie_labels = []
    pie_sizes = []
    pie_colors = []
    if n_nonsyn > 0:
        pie_labels.append(f"Nonsynonymous\n({n_nonsyn})")
        pie_sizes.append(n_nonsyn)
        pie_colors.append("#e74c3c")
    if n_syn > 0:
        pie_labels.append(f"Synonymous\n({n_syn})")
        pie_sizes.append(n_syn)
        pie_colors.append("#3498db")
    if n_start > 0:
        pie_labels.append(f"Start gain\n({n_start})")
        pie_sizes.append(n_start)
        pie_colors.append("#f39c12")
    if n_stop > 0:
        pie_labels.append(f"Stop removal\n({n_stop})")
        pie_sizes.append(n_stop)
        pie_colors.append("#9b59b6")

    if pie_sizes:
        wedges, texts, autotexts = ax2.pie(
            pie_sizes, labels=pie_labels, colors=pie_colors,
            autopct="%1.1f%%", startangle=90, textprops={"fontsize": 9},
        )
        for autotext in autotexts:
            autotext.set_fontsize(8)
    ax2.set_title("Editing type distribution")

    # Panel 3: Codon position distribution
    ax3 = axes[2]
    pos_labels = ["Position 1", "Position 2", "Position 3"]
    pos_values = [codon_counts.get(1, 0), codon_counts.get(2, 0), codon_counts.get(3, 0)]
    pos_colors = ["#e74c3c", "#f39c12", "#3498db"]
    bars = ax3.bar(pos_labels, pos_values, color=pos_colors, edgecolor="black")
    for bar, val in zip(bars, pos_values):
        ax3.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
            str(val), ha="center", va="bottom", fontsize=10, fontweight="bold",
        )
    ax3.set_ylabel("Number of sites")
    ax3.set_title("Codon position distribution")

    fig.tight_layout()
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    logger.info("Wrote editing summary plot: %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_gene_name(feat) -> str | None:
    """Extract gene name from a CDS feature."""
    from Bio.SeqFeature import SeqFeature
    name = feat.qualifiers.get("gene", [None])[0]
    if not name:
        name = feat.qualifiers.get("locus_tag", [None])[0]
    if name:
        name = name.lower().split(".")[0]
    return name


def _apply_edits_to_cds(cds_seq: str, sites: list[EditingSite]) -> str:
    """Apply C-to-U editing sites to a CDS nucleotide sequence.

    Args:
        cds_seq: Original CDS sequence.
        sites: List of EditingSite objects for this gene.

    Returns:
        Corrected CDS nucleotide sequence.
    """
    corrected = list(cds_seq.upper())
    for site in sites:
        pos = site.position_cds - 1  # 0-based
        if pos < len(corrected) and corrected[pos] == "C":
            corrected[pos] = "T"
    return "".join(corrected)


def _translate(seq: str) -> str:
    """Translate nucleotide sequence using NCBI Table 1."""
    CODON_TABLE = {
        "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
        "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
        "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
        "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
        "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
        "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
        "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
        "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
        "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
        "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
        "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
        "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
        "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
        "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
        "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
        "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
    }
    protein = []
    seq = seq.upper()
    for i in range(0, len(seq) - 2, 3):
        codon = seq[i:i + 3]
        if len(codon) < 3:
            break
        aa = CODON_TABLE.get(codon, "X")
        protein.append(aa)
        if aa == "*":
            break
    return "".join(protein)


def _protein_description(gene_name: str, sites: list[EditingSite] | None) -> str:
    """Build FASTA description for a corrected protein."""
    desc = f" corrected protein"
    if sites:
        desc += f" | editing_sites={len(sites)}"
        nonsyn = sum(1 for s in sites if not s.is_synonymous)
        desc += f" nonsynonymous={nonsyn}"
        if any(s.is_start_codon_creation for s in sites):
            desc += " start_codon_gain"
        if any(s.is_stop_codon_removal for s in sites):
            desc += " stop_codon_removal"
    return desc


def _cds_description(gene_name: str, sites: list[EditingSite] | None) -> str:
    """Build FASTA description for a corrected CDS."""
    desc = f" corrected CDS"
    if sites:
        desc += f" | editing_sites={len(sites)}"
        edits = ";".join(f"C{T}@{s.position_cds}" for s in sites)
        desc += f" edits=[{edits}]"
    return desc
