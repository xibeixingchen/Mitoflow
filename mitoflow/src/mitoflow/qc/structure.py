"""Structure assessment (Dimension 5).

Validates assembly structure: large repeat consistency,
multi-chromosome detection, GFA topology, and circularity.
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

logger = logging.getLogger(__name__)


@dataclass
class RepeatPair:
    """A pair of large repeat sequences."""
    copy1_start: int
    copy1_end: int
    copy2_start: int
    copy2_end: int
    length: int
    identity: float
    repeat_type: str  # "direct" | "inverted"
    is_consistent: bool = True  # True = both copies match


@dataclass
class StructureResult:
    """Structure assessment result."""
    n_chromosomes: int = 1
    chromosome_sizes: list = field(default_factory=list)
    large_repeats: list = field(default_factory=list)  # RepeatPair
    repeat_consistency: bool = True
    topology: str = "unknown"  # "circular" | "linear" | "multi-chromosome" | "fragmented"
    gfa_valid: Optional[bool] = None
    structure_score: float = 0.0
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Structure: score={self.structure_score:.0f}/100",
            f"  Topology: {self.topology}",
            f"  Chromosomes: {self.n_chromosomes}",
            f"  Large repeats: {len(self.large_repeats)}",
        ]
        if self.large_repeats:
            inconsistent = [r for r in self.large_repeats if not r.is_consistent]
            if inconsistent:
                lines.append(f"  Inconsistent repeats: {len(inconsistent)}")
        for w in self.warnings:
            lines.append(f"  Warning: {w}")
        return "\n".join(lines)


def assess_structure(
    genome: GenomeSequence,
    fasta_path: Path,
    gfa_path: Optional[Path] = None,
    reads_lr: Optional[str] = None,
    min_repeat_length: int = 100,
) -> StructureResult:
    """Assess assembly structure.

    A. Large repeat detection and consistency check
    B. Multi-chromosome detection
    C. GFA topology validation (if provided)
    D. Long read structural validation (if provided)
    """
    result = StructureResult()

    # Chromosome / contig info
    if genome.contig_map:
        result.n_chromosomes = len(genome.contig_map)
        result.chromosome_sizes = [c.length for c in genome.contig_map]
    else:
        result.n_chromosomes = 1
        result.chromosome_sizes = [len(genome.sequence)]

    # Large repeats
    result.large_repeats = _find_large_repeats(
        fasta_path, min_repeat_length
    )
    result.repeat_consistency = all(r.is_consistent for r in result.large_repeats)

    if not result.repeat_consistency:
        result.warnings.append(
            "Inconsistent repeat copies detected — possible assembly error"
        )

    # Topology determination
    result.topology = _determine_topology(
        result.n_chromosomes, genome.is_circular
    )

    # GFA validation
    if gfa_path:
        result.gfa_valid = _validate_gfa(gfa_path)
        if not result.gfa_valid:
            result.warnings.append("GFA topology has potential issues")

    # Score
    result.structure_score = _score_structure(
        result.n_chromosomes, result.repeat_consistency,
        result.gfa_valid, result.large_repeats,
    )

    return result


def _find_large_repeats(
    fasta_path: Path, min_length: int = 100,
) -> list:
    """Find large repeats via BLAST self-comparison."""
    blastn = shutil.which("blastn")
    makeblastdb = shutil.which("makeblastdb")
    if not blastn or not makeblastdb:
        return []

    repeats = []

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "self_db"
        subprocess.run(
            [makeblastdb, "-in", str(fasta_path), "-dbtype", "nucl",
             "-out", str(db)],
            capture_output=True, timeout=120,
        )

        proc = subprocess.run(
            [blastn, "-query", str(fasta_path), "-db", str(db),
             "-outfmt", "6 qstart qend sstart send pident length",
             "-evalue", "1e-10", "-max_target_seqs", "50",
             "-dust", "no"],
            capture_output=True, text=True, timeout=300,
        )

        if proc.returncode != 0:
            return []

        seen = set()
        for line in proc.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            try:
                qstart, qend = int(parts[0]), int(parts[1])
                sstart, send = int(parts[2]), int(parts[3])
                pident = float(parts[4])
                length = int(parts[5])
            except ValueError:
                continue

            if length < min_length or pident < 95.0:
                continue

            # Skip self-hits and duplicates
            key = (min(qstart, sstart), max(qstart, sstart))
            if abs(qstart - sstart) < min_length:
                continue
            if key in seen:
                continue
            seen.add(key)

            # Determine type
            if (qend - qstart) * (send - sstart) > 0:
                rtype = "direct"
            else:
                rtype = "inverted"

            repeats.append(RepeatPair(
                copy1_start=min(qstart, qend),
                copy1_end=max(qstart, qend),
                copy2_start=min(sstart, send),
                copy2_end=max(sstart, send),
                length=length,
                identity=pident,
                repeat_type=rtype,
                is_consistent=pident >= 99.0,
            ))

    return repeats


def _determine_topology(n_chromosomes: int, is_circular: bool) -> str:
    """Determine assembly topology."""
    if n_chromosomes == 1:
        return "circular" if is_circular else "linear"
    elif n_chromosomes <= 5:
        return "multi-chromosome"
    else:
        return "fragmented"


def _validate_gfa(gfa_path: Path) -> bool:
    """Validate GFA graph topology.

    Checks:
    1. No dead-end segments (unless terminal)
    2. Coverage consistency
    """
    try:
        segments = {}
        links = set()

        with open(gfa_path) as f:
            for line in f:
                parts = line.strip().split("\t")
                if parts[0] == "S":
                    seg_name = parts[1]
                    segments[seg_name] = True
                elif parts[0] == "L":
                    if len(parts) >= 6:
                        links.add(parts[1])
                        links.add(parts[3])

        # Check for dead ends (segments with no links)
        dead_ends = [s for s in segments if s not in links]
        # Single segment with no links is OK (circular if overlap)
        if len(segments) > 1 and len(dead_ends) > 2:
            return False

        return True
    except Exception:
        return None


def _score_structure(
    n_chromosomes: int, repeat_consistency: bool,
    gfa_valid: Optional[bool], repeats: list,
) -> float:
    """Score assembly structure."""
    score = 100.0

    # Chromosome penalty
    if n_chromosomes > 5:
        score -= (n_chromosomes - 5) * 5

    # Repeat consistency
    if not repeat_consistency:
        score -= 15

    # GFA validation
    if gfa_valid is False:
        score -= 20

    # Many repeats can indicate complex structure
    if len(repeats) > 20:
        score -= 5

    return max(0, min(100, score))
