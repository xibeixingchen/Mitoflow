"""Phylogenetic analysis helper — automates sequence extraction and alignment.

Does NOT build trees (user chooses IQ-TREE/RAxML). Instead automates:
1. Extract shared gene sequences from multiple GenBank files
2. Per-gene MAFFT alignment + trimAl trimming
3. Concatenate into supermatrix
4. Write partition files (IQ-TREE / RAxML format)
"""

from __future__ import annotations
import logging
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PhyloResult:
    """Result of phylogenetic alignment preparation."""
    species_names: list = field(default_factory=list)
    shared_genes: list = field(default_factory=list)
    gene_presence: dict = field(default_factory=dict)  # gene -> {species: bool}
    output_files: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=== Phylogenetic Alignment ===",
            f"Species: {len(self.species_names)}",
            f"Shared genes: {len(self.shared_genes)}",
        ]
        if self.gene_presence:
            for gene in self.shared_genes:
                present = sum(1 for v in self.gene_presence.get(gene, {}).values() if v)
                lines.append(f"  {gene}: {present}/{len(self.species_names)}")
        if self.output_files:
            lines.append("")
            for ftype, fpath in self.output_files.items():
                lines.append(f"  {ftype}: {fpath}")
        return "\n".join(lines)


def extract_shared_genes(
    genbank_files: list,
    species_names: Optional[list] = None,
    sequence_type: str = "protein",
    min_presence: float = 1.0,
) -> tuple:
    """Extract shared gene sequences from multiple GenBank files.

    Args:
        genbank_files: List of GenBank file paths.
        species_names: Optional species names.
        sequence_type: "protein" or "nucleotide".
        min_presence: Minimum fraction of species that must have the gene.

    Returns:
        (gene_sequences, species_names, shared_genes)
        gene_sequences: {gene: {species: sequence}}
    """
    from Bio import SeqIO

    n = len(genbank_files)
    names = species_names or [f"species_{i}" for i in range(n)]

    # Extract per-gene sequences per species
    gene_seqs = defaultdict(dict)  # gene -> {species: seq}

    for i, gbk_path in enumerate(genbank_files):
        sp = names[i]
        record = next(SeqIO.parse(str(gbk_path), "genbank"))

        for feat in record.features:
            if feat.type != "CDS":
                continue

            gname = feat.qualifiers.get("gene",
                     feat.qualifiers.get("locus_tag", [None]))[0]
            if not gname:
                continue
            gname = gname.lower().split(".")[0]

            try:
                if sequence_type == "protein":
                    if "translation" in feat.qualifiers:
                        seq = feat.qualifiers["translation"][0]
                    else:
                        cds = str(feat.extract(record.seq)).upper()
                        seq = _translate(cds)
                else:
                    seq = str(feat.extract(record.seq)).upper()
                    # Remove stop codon
                    if len(seq) % 3 == 0 and seq[-3:] in ("TAA", "TAG", "TGA"):
                        seq = seq[:-3]

                if seq:
                    gene_seqs[gname][sp] = seq
            except Exception:
                continue

    # Filter by min_presence
    threshold = min_presence * n
    shared = sorted(
        g for g, seqs in gene_seqs.items()
        if len(seqs) >= threshold
    )

    return gene_seqs, names, shared


def align_and_concatenate(
    genbank_files: list,
    output_dir: Path,
    species_names: Optional[list] = None,
    sequence_type: str = "protein",
    aligner: str = "mafft",
    trim: bool = True,
    min_presence: float = 1.0,
    output_formats: Optional[list] = None,
) -> PhyloResult:
    """Extract shared genes, align per-gene, trim, concatenate.

    Outputs:
    - concatenated.phy / .fasta
    - partition.txt (IQ-TREE)
    - partition.raxml (RAxML)
    - gene_presence_matrix.tsv
    - per_gene/ aligned sequences

    Args:
        genbank_files: List of GenBank files.
        output_dir: Output directory.
        species_names: Optional species names.
        sequence_type: "protein" or "nucleotide".
        aligner: Alignment tool ("mafft" or "muscle").
        trim: Whether to trim with trimAl.
        min_presence: Minimum gene presence fraction.
        output_formats: Output formats ["phylip", "fasta", "nexus"].

    Returns:
        PhyloResult with file paths and statistics.
    """
    if output_formats is None:
        output_formats = ["phylip", "fasta"]

    result = PhyloResult()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract sequences
    gene_seqs, names, shared = extract_shared_genes(
        genbank_files, species_names, sequence_type, min_presence,
    )

    result.species_names = names
    result.shared_genes = shared

    if not shared:
        result.warnings.append("No shared genes found across all species")
        return result

    # Gene presence matrix
    for gene in shared:
        result.gene_presence[gene] = {}
        for sp in names:
            result.gene_presence[gene][sp] = sp in gene_seqs.get(gene, {})

    # Per-gene alignment
    gene_dir = output_dir / "per_gene"
    gene_dir.mkdir(exist_ok=True)

    aligned_seqs = {}  # gene -> {species: aligned_seq}
    partitions = []    # (gene, start, end)

    concat_offset = 0

    for gene in shared:
        seqs = gene_seqs.get(gene, {})
        if len(seqs) < 2:
            continue

        # Align
        aligned = _align_sequences(seqs, names, gene_dir / f"{gene}.fasta", aligner)

        # Trim
        if trim and len(aligned) > 0:
            aligned = _trim_alignment(aligned, gene_dir / f"{gene}.fasta")

        if not aligned:
            continue

        aligned_seqs[gene] = aligned

        # Record partition
        seq_len = len(next(iter(aligned.values())))
        partitions.append((gene, concat_offset + 1, concat_offset + seq_len))
        concat_offset += seq_len

    if not aligned_seqs:
        result.warnings.append("No alignments produced")
        return result

    # Concatenate
    concatenated = _concatenate_alignments(aligned_seqs, names, shared)

    # Write outputs
    for fmt in output_formats:
        if fmt == "phylip":
            phy_path = output_dir / "concatenated.phy"
            _write_phylip(concatenated, names, phy_path)
            result.output_files["phylip"] = phy_path
        elif fmt == "fasta":
            fa_path = output_dir / "concatenated.fasta"
            _write_fasta(concatenated, names, fa_path)
            result.output_files["fasta"] = fa_path

    # Partition files
    partition_path = output_dir / "partition.txt"
    _write_iqtree_partition(partitions, partition_path)
    result.output_files["partition_iqtree"] = partition_path

    raxml_path = output_dir / "partition.raxml"
    _write_raxml_partition(partitions, sequence_type, raxml_path)
    result.output_files["partition_raxml"] = raxml_path

    # Gene presence matrix
    matrix_path = output_dir / "gene_presence_matrix.tsv"
    _write_presence_matrix(result.gene_presence, shared, names, matrix_path)
    result.output_files["presence_matrix"] = matrix_path

    return result


# ── Internal helpers ─────────────────────────────────────────────

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


def _translate(seq: str) -> str:
    protein = []
    for i in range(0, len(seq) - 2, 3):
        codon = seq[i:i + 3]
        aa = CODON_TABLE.get(codon, "X")
        if aa == "*":
            break
        protein.append(aa)
    return "".join(protein)


def _align_sequences(seqs: dict, names: list, out_path: Path, aligner: str) -> dict:
    """Align sequences using MAFFT or return unaligned."""
    tool = shutil.which(aligner)
    if not tool:
        # No aligner — return padded sequences
        max_len = max(len(s) for s in seqs.values()) if seqs else 0
        return {sp: seqs.get(sp, "-" * max_len).ljust(max_len, "-") for sp in names}

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        fa_in = tmp / "input.fasta"

        with open(fa_in, "w") as f:
            for sp in names:
                seq = seqs.get(sp, "")
                if seq:
                    f.write(f">{sp}\n{seq}\n")

        try:
            proc = subprocess.run(
                [tool, "--auto", "--quiet", str(fa_in)],
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode == 0:
                from Bio import SeqIO
                import io
                aligned = {}
                records = SeqIO.parse(io.StringIO(proc.stdout), "fasta")
                for rec in records:
                    aligned[rec.id] = str(rec.seq)

                # Write aligned output
                with open(out_path, "w") as f:
                    f.write(proc.stdout)

                return aligned
        except (subprocess.TimeoutExpired, Exception) as e:
            logger.debug(f"Alignment failed for {out_path.name}: {e}")

    return {}


def _trim_alignment(aligned: dict, fa_path: Path) -> dict:
    """Trim alignment with trimAl if available."""
    trimal = shutil.which("trimal")
    if not trimal:
        return aligned

    if not fa_path.exists():
        return aligned

    try:
        out_path = fa_path.parent / (fa_path.stem + "_trimmed.fasta")
        proc = subprocess.run(
            [trimal, "-in", str(fa_path), "-out", str(out_path),
             "-automated1"],
            capture_output=True, timeout=60,
        )
        if proc.returncode == 0 and out_path.exists():
            from Bio import SeqIO
            trimmed = {}
            for rec in SeqIO.parse(str(out_path), "fasta"):
                trimmed[rec.id] = str(rec.seq)
            return trimmed if trimmed else aligned
    except Exception:
        pass

    return aligned


def _concatenate_alignments(
    aligned_seqs: dict, names: list, genes: list,
) -> dict:
    """Concatenate per-gene alignments into supermatrix."""
    concat = {sp: "" for sp in names}

    for gene in genes:
        gene_aligned = aligned_seqs.get(gene, {})
        if not gene_aligned:
            # Get alignment length from any available sequence
            continue

        # Get alignment length
        ref_len = len(next(iter(gene_aligned.values())))

        for sp in names:
            seq = gene_aligned.get(sp, "-" * ref_len)
            # Pad if needed
            if len(seq) < ref_len:
                seq = seq + "-" * (ref_len - len(seq))
            elif len(seq) > ref_len:
                seq = seq[:ref_len]
            concat[sp] += seq

    return concat


def _write_phylip(concatenated: dict, names: list, path: Path) -> None:
    """Write PHYLIP format."""
    n_taxa = len(names)
    n_sites = len(next(iter(concatenated.values())))

    with open(path, "w") as f:
        f.write(f" {n_taxa} {n_sites}\n")
        for sp in names:
            seq = concatenated.get(sp, "")
            # PHYLIP: name exactly 10 chars, padded
            name = sp[:10].ljust(10)
            f.write(f"{name}{seq}\n")


def _write_fasta(concatenated: dict, names: list, path: Path) -> None:
    """Write FASTA format."""
    with open(path, "w") as f:
        for sp in names:
            seq = concatenated.get(sp, "")
            f.write(f">{sp}\n{seq}\n")


def _write_iqtree_partition(partitions: list, path: Path) -> None:
    """Write IQ-TREE partition file."""
    with open(path, "w") as f:
        for gene, start, end in partitions:
            f.write(f"{gene}, part_{gene} = {start}-{end}\n")


def _write_raxml_partition(partitions: list, seq_type: str, path: Path) -> None:
    """Write RAxML partition file."""
    dtype = "AA" if seq_type == "protein" else "DNA"
    with open(path, "w") as f:
        for gene, start, end in partitions:
            f.write(f"{dtype}, part_{gene} = {start}-{end}\n")


def _write_presence_matrix(
    presence: dict, genes: list, names: list, path: Path,
) -> None:
    """Write gene presence/absence matrix."""
    with open(path, "w") as f:
        f.write("gene\t" + "\t".join(names) + "\n")
        for gene in genes:
            values = ["1" if presence.get(gene, {}).get(sp, False) else "0"
                      for sp in names]
            f.write(gene + "\t" + "\t".join(values) + "\n")
