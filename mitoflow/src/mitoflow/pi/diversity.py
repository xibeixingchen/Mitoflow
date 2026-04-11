"""Nucleotide diversity (Pi) calculation for mitochondrial genome comparison.

Computes Pi for CDS and intergenic spacer (IGS) regions across multiple
species. Identifies evolutionary hotspots (high Pi) useful for barcoding
and phylogenetic markers.
"""

from __future__ import annotations

import io
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

logger = logging.getLogger(__name__)


@dataclass
class PiRegionResult:
    """Pi result for a single genomic region."""
    name: str           # gene or IGS name
    region_type: str     # "CDS" or "IGS"
    pi: float           # nucleotide diversity
    n_sequences: int     # number of sequences compared
    length: int          # alignment length (bp)
    n_variable_sites: int = 0
    n_parsimony_sites: int = 0

    @property
    def is_hotspot(self) -> bool:
        """A region is a hotspot if Pi > 0.01 (commonly used threshold)."""
        return self.pi > 0.01


@dataclass
class PiResult:
    """Complete nucleotide diversity analysis result."""
    regions: list[PiRegionResult] = field(default_factory=list)
    n_species: int = 0
    n_shared_cds: int = 0
    n_shared_igs: int = 0
    mean_pi_cds: float = 0.0
    mean_pi_igs: float = 0.0
    hotspot_cds: list[str] = field(default_factory=list)
    hotspot_igs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=== Nucleotide Diversity (Pi) Analysis ===",
            f"Species compared: {self.n_species}",
            f"Shared CDS regions: {self.n_shared_cds}",
            f"Shared IGS regions: {self.n_shared_igs}",
            f"Mean Pi (CDS): {self.mean_pi_cds:.6f}",
            f"Mean Pi (IGS): {self.mean_pi_igs:.6f}",
        ]
        if self.hotspot_cds:
            lines.append(f"Hotspot CDS (Pi>0.01): {', '.join(self.hotspot_cds)}")
        if self.hotspot_igs:
            lines.append(f"Hotspot IGS (Pi>0.01): {', '.join(self.hotspot_igs)}")
        if self.warnings:
            for w in self.warnings:
                lines.append(f"  Warning: {w}")
        return "\n".join(lines)


def _extract_cds_from_gbk(gbk_path: Path) -> dict[str, str]:
    """Extract CDS sequences from a GenBank file."""
    record = SeqIO.read(str(gbk_path), "genbank")
    cds = {}
    for feat in record.features:
        if feat.type != "CDS":
            continue
        name = feat.qualifiers.get("gene", feat.qualifiers.get("locus_tag", [""]))[0]
        if not name:
            continue
        try:
            seq = str(feat.extract(record.seq)).upper()
            if len(seq) >= 3:
                cds[name.lower()] = seq
        except Exception:
            continue
    return cds


def _extract_igs_from_gbk(gbk_path: Path) -> dict[str, str]:
    """Extract intergenic spacer (IGS) sequences from a GenBank file.

    IGS regions are named by their flanking genes: "geneA_geneB".
    """
    record = SeqIO.read(str(gbk_path), "genbank")
    genome_seq = str(record.seq).upper()
    genome_len = len(genome_seq)

    # Collect all gene positions
    gene_positions = []
    for feat in record.features:
        if feat.type not in ("gene", "CDS", "tRNA", "rRNA"):
            continue
        name = feat.qualifiers.get("gene", feat.qualifiers.get("locus_tag", [""]))[0]
        if not name:
            continue
        start = int(feat.location.start)
        end = int(feat.location.end)
        gene_positions.append((start, end, name.lower()))

    # Sort by start position
    gene_positions.sort(key=lambda x: x[0])

    # Extract intergenic regions
    igs = {}
    for i in range(len(gene_positions) - 1):
        _, end_a, name_a = gene_positions[i]
        start_b, _, name_b = gene_positions[i + 1]
        if start_b > end_a:
            igs_name = f"{name_a}_{name_b}"
            igs_seq = genome_seq[end_a:start_b]
            if len(igs_seq) >= 10:  # Minimum 10 bp
                igs[igs_name] = igs_seq
    return igs


def _align_sequences(sequences: dict[str, str]) -> dict[str, str]:
    """Align sequences using MAFFT.

    Args:
        sequences: dict of name -> sequence

    Returns:
        dict of name -> aligned sequence
    """
    mafft = shutil.which("mafft")
    if not mafft:
        logger.warning("MAFFT not found, sequences compared without alignment")
        return sequences

    with tempfile.TemporaryDirectory(prefix="mitoflow_pi_") as tmpdir:
        # Write input FASTA
        input_fasta = Path(tmpdir) / "input.fasta"
        with open(input_fasta, "w") as f:
            for name, seq in sequences.items():
                f.write(f">{name}\n{seq}\n")

        # Run MAFFT
        cmd = [mafft, "--auto", "--quiet", str(input_fasta)]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120, check=False,
            )
            if result.returncode != 0:
                logger.warning("MAFFT failed: %s", result.stderr)
                return sequences
        except subprocess.TimeoutExpired:
            logger.warning("MAFFT timed out")
            return sequences

        # Parse output
        aligned = {}
        for record in SeqIO.parse(io.StringIO(result.stdout), "fasta"):
            aligned[record.id] = str(record.seq).upper()

    return aligned


def _calculate_pi_from_alignment(aligned_seqs: list[str]) -> float:
    """Calculate nucleotide diversity (Pi) from aligned sequences.

    Pi = average number of pairwise differences / alignment length
    Formula: Pi = (n/(n-1)) * sum_i(p_i * (1-p_i)) * 2
    where p_i = frequency of most common base at site i, n = number of sequences.

    More precisely: Pi = sum over sites of [2*n_i*(n-n_i)] / [n*(n-1)]
    summed across all base types at each site, then divided by alignment length.
    """
    n = len(aligned_seqs)
    if n < 2:
        return 0.0

    length = len(aligned_seqs[0])
    total_pi = 0.0

    for pos in range(length):
        bases = [seq[pos] for seq in aligned_seqs if pos < len(seq) and seq[pos] not in ("-", "N", "?")]
        m = len(bases)
        if m < 2:
            continue

        # Count base frequencies
        from collections import Counter
        counts = Counter(bases)
        site_pi = 0.0
        for base, count in counts.items():
            site_pi += 2 * count * (m - count)
        site_pi /= (m * (m - 1))
        total_pi += site_pi

    return total_pi / length if length > 0 else 0.0


def calculate_pi(
    sequences_by_species: dict[str, dict[str, str]],
    region_type: str = "CDS",
    min_length: int = 30,
) -> PiResult:
    """Calculate nucleotide diversity across species for shared regions.

    Args:
        sequences_by_species: dict of species_name -> {region_name -> sequence}
        region_type: "CDS" or "IGS"
        min_length: Minimum sequence length to include

    Returns:
        PiResult with diversity values per region.
    """
    species_names = list(sequences_by_species.keys())
    n_species = len(species_names)
    if n_species < 2:
        return PiResult(
            n_species=n_species,
            warnings=["Need >= 2 species for Pi calculation"],
        )

    # Find shared regions
    region_sets = [set(seqs.keys()) for seqs in sequences_by_species.values()]
    shared_regions = set.intersection(*region_sets) if region_sets else set()

    if not shared_regions:
        return PiResult(
            n_species=n_species,
            warnings=["No shared regions found across all species"],
        )

    result = PiResult(n_species=n_species)

    for region_name in sorted(shared_regions):
        # Collect sequences for this region
        region_seqs = {}
        for sp in species_names:
            seq = sequences_by_species[sp].get(region_name, "")
            if len(seq) >= min_length:
                region_seqs[sp] = seq

        if len(region_seqs) < 2:
            continue

        # Align
        aligned = _align_sequences(region_seqs)

        # Calculate Pi
        aligned_list = list(aligned.values())
        pi_value = _calculate_pi_from_alignment(aligned_list)

        # Variable sites
        n_variable = 0
        length = len(aligned_list[0]) if aligned_list else 0
        for pos in range(length):
            bases = set(seq[pos] for seq in aligned_list if pos < len(seq) and seq[pos] not in ("-", "N"))
            if len(bases) > 1:
                n_variable += 1

        region_result = PiRegionResult(
            name=region_name,
            region_type=region_type,
            pi=pi_value,
            n_sequences=len(aligned_list),
            length=length,
            n_variable_sites=n_variable,
        )
        result.regions.append(region_result)

    # Summaries
    cds_regions = [r for r in result.regions if r.region_type == "CDS"]
    igs_regions = [r for r in result.regions if r.region_type == "IGS"]

    result.n_shared_cds = len(cds_regions)
    result.n_shared_igs = len(igs_regions)
    result.mean_pi_cds = np.mean([r.pi for r in cds_regions]) if cds_regions else 0
    result.mean_pi_igs = np.mean([r.pi for r in igs_regions]) if igs_regions else 0
    result.hotspot_cds = [r.name for r in cds_regions if r.is_hotspot]
    result.hotspot_igs = [r.name for r in igs_regions if r.is_hotspot]

    return result


def calculate_pi_from_genbank(
    genbank_files: list[Path],
    species_names: Optional[list[str]] = None,
    min_length: int = 30,
) -> PiResult:
    """Calculate nucleotide diversity from multiple GenBank files.

    Extracts CDS and IGS, finds shared regions, aligns with MAFFT,
    and computes Pi for each region.

    Args:
        genbank_files: List of GenBank file paths (>= 2).
        species_names: Display names for each species.
        min_length: Minimum sequence length to include.

    Returns:
        PiResult with per-region diversity values.
    """
    if len(genbank_files) < 2:
        return PiResult(warnings=["Need >= 2 GenBank files for Pi analysis"])

    if not species_names:
        species_names = [Path(f).stem for f in genbank_files]

    # Extract CDS and IGS from each GenBank
    cds_by_species: dict[str, dict[str, str]] = {}
    igs_by_species: dict[str, dict[str, str]] = {}

    for gbk_path, sp_name in zip(genbank_files, species_names):
        cds_by_species[sp_name] = _extract_cds_from_gbk(gbk_path)
        igs_by_species[sp_name] = _extract_igs_from_gbk(gbk_path)

    # Calculate Pi for CDS and IGS
    cds_result = calculate_pi(cds_by_species, region_type="CDS", min_length=min_length)
    igs_result = calculate_pi(igs_by_species, region_type="IGS", min_length=min_length)

    # Merge results
    combined = PiResult(
        regions=cds_result.regions + igs_result.regions,
        n_species=len(species_names),
        n_shared_cds=cds_result.n_shared_cds,
        n_shared_igs=igs_result.n_shared_igs,
        mean_pi_cds=cds_result.mean_pi_cds,
        mean_pi_igs=igs_result.mean_pi_igs,
        hotspot_cds=cds_result.hotspot_cds,
        hotspot_igs=igs_result.hotspot_igs,
        warnings=cds_result.warnings + igs_result.warnings,
    )

    return combined


def write_pi_tables(result: PiResult, output_dir: Path, prefix: str = "mitoflow") -> dict[str, Path]:
    """Write Pi results to TSV files.

    Produces:
      - {prefix}_pi.tsv: full results table
      - {prefix}_pi_summary.txt: text summary
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}

    # Full TSV
    tsv_path = output_dir / f"{prefix}_pi.tsv"
    with open(tsv_path, "w") as f:
        f.write("region\ttype\tpi\tn_sequences\tlength\tvariable_sites\thotspot\n")
        for r in result.regions:
            f.write(f"{r.name}\t{r.region_type}\t{r.pi:.6f}\t{r.n_sequences}\t"
                    f"{r.length}\t{r.n_variable_sites}\t{'Yes' if r.is_hotspot else 'No'}\n")
    files["pi_tsv"] = tsv_path

    # Summary
    summary_path = output_dir / f"{prefix}_pi_summary.txt"
    summary_path.write_text(result.summary() + "\n")
    files["pi_summary"] = summary_path

    return files
