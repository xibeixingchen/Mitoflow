"""Contiguity assessment (Dimension 2).

Evaluates assembly contiguity: contig count, N50, circularity, etc.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models.genome import GenomeSequence

logger = logging.getLogger(__name__)


@dataclass
class ContiguityResult:
    """Result of contiguity assessment."""
    total_length: int = 0
    n_contigs: int = 0
    n50: int = 0
    l50: int = 0
    largest_contig: int = 0
    smallest_contig: int = 0
    gc_content: float = 0.0
    n_count: int = 0
    is_circular: Optional[bool] = None
    overlap_length: int = 0
    n_chromosomes_likely: int = 1
    contiguity_score: float = 0.0  # 0-100
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        circ = "Yes" if self.is_circular else "No"
        lines = [
            f"Contiguity: {self.n_contigs} contig(s), N50={self.n50:,}",
            f"  Total: {self.total_length:,} bp",
            f"  GC: {self.gc_content:.1f}%  N: {self.n_count}",
            f"  Circular: {circ}" + (f" (overlap={self.overlap_length}bp)" if self.overlap_length else ""),
            f"  Score: {self.contiguity_score:.0f}/100",
        ]
        for w in self.warnings:
            lines.append(f"  Warning: {w}")
        return "\n".join(lines)


def assess_contiguity(
    genome: GenomeSequence,
    fasta_path: Optional[Path] = None,
    check_circularity: bool = True,
    overlap_min_length: int = 50,
) -> ContiguityResult:
    """Assess assembly contiguity.

    Scoring:
    - Single contig + circular = 100
    - Single contig + linear = 90
    - 2-3 contigs = 70-80 (may be multi-chromosome)
    - 4-10 contigs = 40-60
    - >10 contigs = 0-30 (likely fragmented)

    Note: Plant mitochondria can have multi-chromosome structure
    (e.g. Silene has up to 128), so multi-contig ≠ fragmented.
    """
    result = ContiguityResult()

    seq = genome.sequence.upper()
    result.total_length = len(seq)
    result.gc_content = genome.gc_content
    result.n_count = seq.count("N")

    # Contig info
    if genome.contig_map:
        contigs = genome.contig_map
        result.n_contigs = len(contigs)
        lengths = sorted([c.length for c in contigs], reverse=True)
        result.largest_contig = lengths[0]
        result.smallest_contig = lengths[-1]
        result.n50 = _calc_n50(lengths)
    else:
        result.n_contigs = 1
        result.largest_contig = result.total_length
        result.smallest_contig = result.total_length
        result.n50 = result.total_length

    # Circularity check
    if check_circularity and fasta_path:
        is_circ, overlap = _check_circularity(fasta_path, overlap_min_length)
        result.is_circular = is_circ
        result.overlap_length = overlap

    # Genome size sanity
    if result.total_length < 50_000:
        result.warnings.append(
            f"Genome very short ({result.total_length:,} bp). "
            f"Expected >=50,000 bp for plant mitochondria."
        )
    elif result.total_length > 15_000_000:
        result.warnings.append(
            f"Genome very long ({result.total_length:,} bp). Check for contamination."
        )

    # N content
    n_pct = result.n_count / result.total_length * 100 if result.total_length > 0 else 0
    if n_pct > 5.0:
        result.warnings.append(f"High N content: {n_pct:.1f}%")

    # GC range check (plant mitochondria: 35-55%)
    if not (35.0 <= result.gc_content <= 55.0):
        result.warnings.append(
            f"GC content {result.gc_content:.1f}% outside expected range (35-55%)"
        )

    # Estimate chromosome number
    if result.n_contigs <= 3:
        result.n_chromosomes_likely = result.n_contigs
    else:
        result.n_chromosomes_likely = result.n_contigs

    # Score
    result.contiguity_score = _score_contiguity(
        result.n_contigs, result.is_circular, result.n_count
    )

    return result


def _calc_n50(lengths: list) -> int:
    """Calculate N50 from sorted (descending) contig lengths."""
    total = sum(lengths)
    cumulative = 0
    for i, length in enumerate(lengths):
        cumulative += length
        if cumulative >= total / 2:
            return length
    return lengths[-1] if lengths else 0


def _check_circularity(
    fasta_path: Path, min_overlap: int = 50
) -> tuple:
    """Check if genome has circular overlap (head = tail).

    Returns (is_circular, overlap_length).
    """
    from Bio import SeqIO

    record = next(SeqIO.parse(str(fasta_path), "fasta"))
    seq = str(record.seq).upper()
    length = len(seq)

    if length < 500:
        return False, 0

    # Check for overlap between sequence ends
    check_len = min(5000, length // 4)
    for overlap_len in range(check_len, min_overlap - 1, -1):
        if seq[:overlap_len] == seq[-overlap_len:]:
            return True, overlap_len

    return False, 0


def _score_contiguity(
    n_contigs: int, is_circular: Optional[bool], n_count: int
) -> float:
    """Calculate contiguity score."""
    if n_contigs == 1:
        if is_circular:
            base = 100
        elif is_circular is None:
            base = 95  # Unknown
        else:
            base = 90
    elif n_contigs <= 3:
        base = 80 - (n_contigs - 1) * 5
    elif n_contigs <= 10:
        base = 60 - (n_contigs - 3) * 3
    else:
        base = max(0, 30 - (n_contigs - 10) * 2)

    # N penalty
    if n_count > 0:
        base -= 5

    return max(0, min(100, base))
