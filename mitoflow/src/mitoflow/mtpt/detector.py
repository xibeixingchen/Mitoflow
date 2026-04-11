"""Mitochondrial Plastid-derived DNA Transfer (MTPT) detection.

Detects regions of chloroplast origin embedded in mitochondrial genomes
using BLAST comparison, annotates cp genes within transfers, and
classifies tRNAs as mt-native vs cp-derived.

Typical plant mt genomes contain 1-5% MTPT DNA (1-50 kb total).
"""

from __future__ import annotations
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models.genome import GenomeSequence
from ..models.gene import GeneAnnotation
from ..models.feature import tRNAAnnotation

logger = logging.getLogger(__name__)


@dataclass
class MTPTRegion:
    """A single MTPT (chloroplast-derived) region in the mitochondrial genome."""
    # Mitochondrial coordinates (1-based)
    mito_start: int
    mito_end: int
    # Chloroplast coordinates (1-based)
    cp_start: int
    cp_end: int
    cp_seqid: str = ""
    # Quality metrics
    identity: float = 0.0
    length: int = 0
    evalue: float = 1.0
    bitscore: float = 0.0
    # Annotation
    cp_genes_covered: list[str] = field(default_factory=list)
    has_functional_trna: bool = False
    trna_names: list[str] = field(default_factory=list)
    # Classification
    category: str = ""  # "intact" | "degenerate" | "fragment" | "ancient"
    description: str = ""

    @property
    def mito_length(self) -> int:
        return self.mito_end - self.mito_start + 1


@dataclass
class MTPTResult:
    """Complete MTPT detection result."""
    regions: list[MTPTRegion] = field(default_factory=list)
    total_mtpt_bp: int = 0
    mtpt_pct: float = 0.0          # % of mito genome
    cp_derived_trnas: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=== MTPT Detection Report ===",
            f"Total MTPT regions: {len(self.regions)}",
            f"Total MTPT bp: {self.total_mtpt_bp:,} ({self.mtpt_pct:.2f}% of genome)",
        ]
        for i, r in enumerate(self.regions, 1):
            genes = ", ".join(r.cp_genes_covered) if r.cp_genes_covered else "none"
            lines.append(
                f"  Region {i}: {r.mito_start:,}-{r.mito_end:,} "
                f"({r.mito_length:,} bp, id={r.identity:.1f}%, {r.category})"
                f"  cp genes: [{genes}]"
            )
        if self.cp_derived_trnas:
            lines.append(f"CP-derived tRNAs: {', '.join(self.cp_derived_trnas)}")
        return "\n".join(lines)


# Default cp gene lengths for coverage estimation
CP_GENE_LENGTHS: dict[str, int] = {
    "rbcL": 1426, "matK": 1527, "psbA": 1062, "psbB": 1527,
    "psbC": 1422, "psbD": 1062, "psbE": 252, "psbF": 126,
    "psbH": 264, "psbI": 228, "psbJ": 141, "psbK": 186,
    "psbL": 114, "psbM": 114, "psbN": 135, "psbT": 84,
    "psaA": 2253, "psaB": 2205, "psaC": 285, "psaI": 111,
    "psaJ": 135,
    "atpA": 1524, "atpB": 1497, "atpE": 411, "atpF": 516,
    "atpH": 249, "atpI": 774,
    "petA": 951, "petB": 798, "petD": 549, "petG": 171,
    "petL": 99, "petN": 93,
    "rpoA": 1014, "rpoB": 3213, "rpoC1": 2022, "rpoC2": 4167,
    "ndhA": 1551, "ndhB": 1506, "ndhC": 357, "ndhD": 1512,
    "ndhE": 306, "ndhF": 2133, "ndhG": 531, "ndhH": 1185,
    "ndhI": 483, "ndhJ": 510, "ndhK": 660,
    "rpl2": 801, "rpl14": 369, "rpl16": 1017, "rpl20": 360,
    "rpl22": 471, "rpl23": 345, "rpl32": 237, "rpl33": 201,
    "rpl36": 120,
    "rps2": 627, "rps3": 705, "rps4": 606, "rps7": 282,
    "rps8": 375, "rps11": 489, "rps12": 378, "rps14": 303,
    "rps15": 324, "rps16": 858, "rps18": 264, "rps19": 282,
    "infA": 228, "clpP": 681, "ycf1": 5400, "ycf2": 6774,
    "ycf3": 456, "ycf4": 573,
}

# Well-known cp-derived tRNAs in plant mitochondria
KNOWN_CP_DERIVED_TRNAS = {
    "trnH-GUG", "trnF-GAA", "trnN-GUU", "trnM-CAU",
    "trnI-CAU", "trnI-GAU", "trnW-CCA", "trnP-UGG",
    "trnA-UGC", "trnR-ACG", "trnL-CAA", "trnV-GAC",
    "trnS-GGA", "trnT-UGU",
}


def detect_mtpt(
    mito_fasta: Path,
    cp_fasta: Path,
    genome: GenomeSequence,
    min_identity: float = 70.0,
    min_length: int = 50,
    merge_distance: int = 200,
    evalue: float = 1e-5,
    threads: int = 4,
) -> MTPTResult:
    """Detect MTPT regions by BLASTing mitochondrial vs chloroplast genome.

    Args:
        mito_fasta: Path to mitochondrial genome FASTA.
        cp_fasta: Path to chloroplast genome FASTA.
        genome: GenomeSequence object for stats.
        min_identity: Minimum percent identity for MTPT.
        min_length: Minimum alignment length.
        merge_distance: Merge hits within this distance.
        evalue: BLAST e-value threshold.
        threads: Number of BLAST threads.

    Returns:
        MTPTResult with all detected regions.
    """
    result = MTPTResult()

    blastn = shutil.which("blastn")
    makeblastdb = shutil.which("makeblastdb")
    if not blastn or not makeblastdb:
        result.warnings.append("BLAST+ not found — MTPT detection skipped")
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cp_db = tmp / "cp_db"

        # Build BLAST db from chloroplast genome
        build_cmd = [
            makeblastdb, "-in", str(cp_fasta), "-dbtype", "nucl",
            "-out", str(cp_db),
        ]
        proc = subprocess.run(build_cmd, capture_output=True, timeout=120)
        if proc.returncode != 0:
            result.warnings.append("Failed to build chloroplast BLAST database")
            return result

        # BLAST mitochondria vs chloroplast
        blast_cmd = [
            blastn, "-query", str(mito_fasta), "-db", str(cp_db),
            "-outfmt",
            "6 qseqid qstart qend sseqid sstart send pident length "
            "mismatch gapopen qseq sseq evalue bitscore",
            "-evalue", str(evalue),
            "-max_target_seqs", "20",
            "-num_threads", str(threads),
            "-dust", "no",  # Don't mask low-complexity
        ]
        proc = subprocess.run(
            blast_cmd, capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            result.warnings.append(f"BLAST failed: {proc.stderr[:200]}")
            return result

        hits = _parse_blast_out(proc.stdout)
        if not hits:
            logger.info("No MTPT hits found")
            return result

        # Merge overlapping hits
        merged = _merge_hits(hits, merge_distance)

        # Filter by thresholds
        for hit in merged:
            if hit["pident"] < min_identity or hit["length"] < min_length:
                continue

            region = MTPTRegion(
                mito_start=min(hit["qstart"], hit["qend"]),
                mito_end=max(hit["qstart"], hit["qend"]),
                cp_start=min(hit["sstart"], hit["send"]),
                cp_end=max(hit["sstart"], hit["send"]),
                cp_seqid=hit["sseqid"],
                identity=hit["pident"],
                length=hit["length"],
                evalue=hit["evalue"],
                bitscore=hit["bitscore"],
            )
            result.regions.append(region)

    # Annotate cp genes in each region
    _annotate_cp_genes(result.regions, cp_fasta)

    # Classify regions
    _classify_regions(result.regions)

    # Compute totals
    result.total_mtpt_bp = sum(r.mito_length for r in result.regions)
    genome_len = len(genome.sequence)
    result.mtpt_pct = result.total_mtpt_bp / genome_len * 100 if genome_len > 0 else 0

    if result.regions:
        logger.info(
            f"Found {len(result.regions)} MTPT regions "
            f"({result.total_mtpt_bp:,} bp, {result.mtpt_pct:.2f}%)"
        )

    return result


def annotate_trna_origin(
    trna_annotations: list[tRNAAnnotation],
    mtpt_regions: list[MTPTRegion],
    genome: GenomeSequence,
) -> list[tRNAAnnotation]:
    """Tag tRNAs as mt-native or cp-derived based on MTPT overlap.

    A tRNA is classified as cp-derived if:
    1. It falls within an MTPT region, OR
    2. Its gene name matches a known cp-derived tRNA AND overlaps MTPT

    Args:
        trna_annotations: List of tRNA annotations.
        mtpt_regions: Detected MTPT regions.
        genome: Genome sequence.

    Returns:
        Updated tRNA annotations with is_cp_derived flags.
    """
    for trna in trna_annotations:
        # Check overlap with any MTPT region
        for region in mtpt_regions:
            if _ranges_overlap(
                trna.genomic_start, trna.genomic_end,
                region.mito_start, region.mito_end,
                min_overlap_pct=50,
            ):
                trna.is_cp_derived = True
                trna.notes = trna.notes + ["CP-derived (MTPT)"]
                break

        # Also check known cp-derived list
        full_name = f"{trna.gene_name}-{trna.anticodon}"
        if full_name in KNOWN_CP_DERIVED_TRNAS and not trna.is_cp_derived:
            # Check if near an MTPT region (within 500bp)
            for region in mtpt_regions:
                if abs(trna.genomic_start - region.mito_start) < 500 or \
                   abs(trna.genomic_end - region.mito_end) < 500:
                    trna.is_cp_derived = True
                    trna.notes = trna.notes + ["CP-derived (near MTPT)"]
                    break

    return trna_annotations


def generate_mtpt_dotplot(
    mito_fasta: Path,
    cp_fasta: Path,
    output_path: Path,
    title: str = "MTPT Dot Plot",
    min_identity: float = 70.0,
) -> Optional[Path]:
    """Generate a dot-plot comparing mitochondrial vs chloroplast genome.

    Creates a matplotlib figure showing alignment positions.

    Args:
        mito_fasta: Mitochondrial genome FASTA.
        cp_fasta: Chloroplast genome FASTA.
        output_path: Output image path (PNG/SVG/PDF).
        title: Plot title.
        min_identity: Minimum identity to plot.

    Returns:
        Path to output file, or None on failure.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        logger.warning("matplotlib not installed, skipping dot-plot")
        return None

    blastn = shutil.which("blastn")
    makeblastdb = shutil.which("makeblastdb")
    if not blastn or not makeblastdb:
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cp_db = tmp / "cp_db"

        subprocess.run(
            [makeblastdb, "-in", str(cp_fasta), "-dbtype", "nucl",
             "-out", str(cp_db)],
            capture_output=True, timeout=120,
        )
        proc = subprocess.run(
            [blastn, "-query", str(mito_fasta), "-db", str(cp_db),
             "-outfmt", "6 qstart qend sstart send pident length bitscore",
             "-evalue", "1e-5", "-dust", "no"],
            capture_output=True, text=True, timeout=600,
        )

        hits = []
        for line in proc.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            try:
                hits.append({
                    "qstart": int(parts[0]), "qend": int(parts[1]),
                    "sstart": int(parts[2]), "send": int(parts[3]),
                    "pident": float(parts[4]),
                    "length": int(parts[5]),
                    "bitscore": float(parts[6]),
                })
            except ValueError:
                continue

    if not hits:
        logger.info("No MTPT hits for dot-plot")
        return None

    # Read sequence lengths
    from Bio import SeqIO
    mito_rec = next(SeqIO.parse(str(mito_fasta), "fasta"))
    cp_rec = next(SeqIO.parse(str(cp_fasta), "fasta"))
    mito_len = len(mito_rec.seq)
    cp_len = len(cp_rec.seq)

    fig, ax = plt.subplots(figsize=(10, 8))

    for hit in hits:
        if hit["pident"] < min_identity:
            continue

        # Determine color by identity
        if hit["pident"] >= 95:
            color = "#d62728"  # red — high identity (recent transfer)
        elif hit["pident"] >= 85:
            color = "#ff7f0e"  # orange
        elif hit["pident"] >= 75:
            color = "#2ca02c"  # green
        else:
            color = "#1f77b4"  # blue — low identity (ancient transfer)

        # Draw line segment
        if hit["sstart"] <= hit["send"]:
            # Same orientation
            ax.plot(
                [hit["qstart"] / 1000, hit["qend"] / 1000],
                [hit["sstart"] / 1000, hit["send"] / 1000],
                color=color, linewidth=1.5, alpha=0.7,
            )
        else:
            # Inverted
            ax.plot(
                [hit["qstart"] / 1000, hit["qend"] / 1000],
                [hit["send"] / 1000, hit["sstart"] / 1000],
                color=color, linewidth=1.5, alpha=0.7, linestyle="--",
            )

    ax.set_xlabel("Mitochondrial genome (kb)")
    ax.set_ylabel("Chloroplast genome (kb)")
    ax.set_title(title)
    ax.set_xlim(0, mito_len / 1000)
    ax.set_ylim(0, cp_len / 1000)

    # Legend
    handles = [
        mpatches.Patch(color="#d62728", label=">=95% identity"),
        mpatches.Patch(color="#ff7f0e", label="85-95%"),
        mpatches.Patch(color="#2ca02c", label="75-85%"),
        mpatches.Patch(color="#1f77b4", label="<75% (ancient)"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8)

    plt.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)

    logger.info(f"MTPT dot-plot saved to {output_path}")
    return output_path


# ── Internal helpers ─────────────────────────────────────────────

def _parse_blast_out(text: str) -> list[dict]:
    """Parse BLAST -outfmt 6 output."""
    hits = []
    for line in text.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 14:
            continue
        try:
            hits.append({
                "qseqid": parts[0],
                "qstart": int(parts[1]),
                "qend": int(parts[2]),
                "sseqid": parts[3],
                "sstart": int(parts[4]),
                "send": int(parts[5]),
                "pident": float(parts[6]),
                "length": int(parts[7]),
                "evalue": float(parts[12]),
                "bitscore": float(parts[13]),
            })
        except (ValueError, IndexError):
            continue
    return hits


def _merge_hits(
    hits: list[dict], merge_distance: int = 200
) -> list[dict]:
    """Merge overlapping or nearby BLAST hits on mitochondrial coords."""
    if not hits:
        return []

    sorted_hits = sorted(hits, key=lambda h: min(h["qstart"], h["qend"]))
    merged = [sorted_hits[0]]

    for hit in sorted_hits[1:]:
        prev = merged[-1]
        prev_start = min(prev["qstart"], prev["qend"])
        prev_end = max(prev["qstart"], prev["qend"])
        curr_start = min(hit["qstart"], hit["qend"])
        curr_end = max(hit["qstart"], hit["qend"])

        if curr_start <= prev_end + merge_distance:
            # Merge: extend boundaries, keep best scores
            merged[-1] = {
                **prev,
                "qstart": min(prev_start, curr_start),
                "qend": max(prev_end, curr_end),
                "sstart": min(prev["sstart"], hit["sstart"]),
                "send": max(prev["send"], hit["send"]),
                "pident": max(prev["pident"], hit["pident"]),
                "length": max(prev_end, curr_end) - min(prev_start, curr_start),
                "bitscore": prev["bitscore"] + hit["bitscore"],
                "evalue": min(prev["evalue"], hit["evalue"]),
            }
        else:
            merged.append(hit)

    return merged


def _annotate_cp_genes(
    regions: list[MTPTRegion], cp_fasta: Path
) -> None:
    """Annotate chloroplast genes within each MTPT region.

    Uses a simple keyword match against known cp gene names to estimate
    which genes are covered by the transfer.
    """
    # Parse cp genome to get gene positions (via BLAST against self is overkill;
    # instead, we estimate coverage from alignment span)
    for region in region_list(regions):
        span = region.cp_end - region.cp_start + 1
        genes_found = []

        for gene_name, gene_len in CP_GENE_LENGTHS.items():
            # Check if gene could be fully contained (>80% covered)
            overlap_start = max(region.cp_start, 1)
            overlap_end = min(region.cp_end, gene_len)
            overlap = overlap_end - overlap_start + 1

            if overlap > gene_len * 0.8:
                genes_found.append(gene_name)

        region.cp_genes_covered = genes_found


def region_list(regions: list[MTPTRegion]) -> list[MTPTRegion]:
    """Type helper to iterate regions."""
    return regions


def _classify_regions(regions: list[MTPTRegion]) -> None:
    """Classify MTPT regions by identity and content.

    Categories:
    - "intact": high identity (>=95%), contains functional cp genes
    - "degenerate": medium identity (85-95%), partial cp genes
    - "fragment": lower identity (70-85%), no recognizable genes
    - "ancient": very low identity (<70%), detected by BLAST only
    """
    for region in regions:
        has_genes = bool(region.cp_genes_covered)
        has_trna = any(
            g.startswith("trn") for g in region.cp_genes_covered
        )
        region.has_functional_trna = has_trna

        if region.identity >= 95 and has_genes:
            region.category = "intact"
            region.description = (
                f"Intact transfer with {len(region.cp_genes_covered)} cp genes"
            )
        elif region.identity >= 85:
            if has_genes:
                region.category = "degenerate"
                region.description = (
                    f"Degenerate transfer, {len(region.cp_genes_covered)} cp genes"
                )
            else:
                region.category = "degenerate"
                region.description = "Degenerate transfer, no recognizable cp genes"
        elif region.identity >= 75:
            region.category = "fragment"
            region.description = "Fragmentary transfer"
        else:
            region.category = "ancient"
            region.description = "Ancient transfer (highly diverged)"


def _ranges_overlap(
    start1: int, end1: int,
    start2: int, end2: int,
    min_overlap_pct: float = 50,
) -> bool:
    """Check if two ranges overlap with minimum percentage of the smaller range."""
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    if overlap_end < overlap_start:
        return False
    overlap_len = overlap_end - overlap_start + 1
    smaller_len = min(end1 - start1 + 1, end2 - start2 + 1)
    return overlap_len >= smaller_len * min_overlap_pct / 100
