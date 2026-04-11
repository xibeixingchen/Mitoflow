"""Correctness assessment (Dimension 3).

Evaluates base-level and structural correctness:
- Coverage uniformity (from BAM, reads, or GFA)
- Base accuracy (from short reads)
- CDS integrity
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
class CoverageResult:
    """Coverage uniformity assessment result."""
    mean_depth: float = 0.0
    median_depth: float = 0.0
    std_depth: float = 0.0
    cv: float = 0.0
    min_depth: int = 0
    max_depth: int = 0
    zero_coverage_regions: list = field(default_factory=list)  # (start, end)
    low_coverage_regions: list = field(default_factory=list)    # <0.2x mean
    high_coverage_regions: list = field(default_factory=list)   # >5x mean
    depth_uniformity_score: float = 0.0
    is_available: bool = False

    def summary(self) -> str:
        if not self.is_available:
            return "Coverage: N/A"
        return (
            f"Coverage: mean={self.mean_depth:.1f}x, median={self.median_depth:.1f}x, "
            f"CV={self.cv:.2f}, score={self.depth_uniformity_score:.0f}/100"
        )


@dataclass
class BaseAccuracyResult:
    """Base-level accuracy result."""
    total_bases: int = 0
    consistent_bases: int = 0
    snp_count: int = 0
    indel_count: int = 0
    consistency_rate: float = 0.0
    qv: float = 0.0
    is_available: bool = False

    def summary(self) -> str:
        if not self.is_available:
            return "Base accuracy: N/A"
        return (
            f"Base accuracy: QV={self.qv:.1f}, "
            f"SNPs={self.snp_count}, INDELs={self.indel_count}"
        )


@dataclass
class CorrectnessResult:
    """Complete correctness assessment."""
    coverage: CoverageResult = field(default_factory=CoverageResult)
    base_accuracy: BaseAccuracyResult = field(default_factory=BaseAccuracyResult)
    correctness_score: float = 0.0

    def summary(self) -> str:
        lines = [f"Correctness: score={self.correctness_score:.0f}/100"]
        lines.append(f"  {self.coverage.summary()}")
        lines.append(f"  {self.base_accuracy.summary()}")
        return "\n".join(lines)


def assess_correctness(
    fasta_path: Path,
    genome: GenomeSequence,
    bam_path: Optional[Path] = None,
    reads_sr: Optional[list] = None,
    reads_lr: Optional[str] = None,
    gfa_path: Optional[Path] = None,
    window_size: int = 500,
    min_depth: int = 10,
) -> CorrectnessResult:
    """Assess correctness of the assembly.

    Priority (inspired by HiMT):
    1. GFA: extract depth from DP/RC/LN tags (fastest)
    2. BAM: samtools depth (per-base)
    3. Reads: minimap2 mapping -> samtools depth

    Args:
        fasta_path: Assembly FASTA.
        genome: GenomeSequence.
        bam_path: Pre-aligned BAM file.
        reads_sr: Short read files [R1, R2].
        reads_lr: Long read file.
        gfa_path: Assembly graph GFA file.
        window_size: Window for coverage analysis.
        min_depth: Minimum depth for base accuracy.

    Returns:
        CorrectnessResult with coverage and accuracy data.
    """
    result = CorrectnessResult()

    # Coverage assessment
    if gfa_path:
        result.coverage = _coverage_from_gfa(gfa_path)
    elif bam_path:
        result.coverage = _coverage_from_bam(bam_path)
    elif reads_sr or reads_lr:
        result.coverage = _coverage_from_reads(
            fasta_path, reads_sr, reads_lr
        )

    # Base accuracy (needs short reads)
    if reads_sr:
        result.base_accuracy = _assess_base_accuracy(
            fasta_path, reads_sr, min_depth
        )

    # Score
    score_parts = []
    if result.coverage.is_available:
        score_parts.append(result.coverage.depth_uniformity_score * 0.6)
    if result.base_accuracy.is_available:
        score_parts.append(min(100, result.base_accuracy.qv) * 0.4)

    if score_parts:
        result.correctness_score = sum(score_parts) / len(score_parts) * 2
        # Normalize to max 100 if we have both parts
        if len(score_parts) == 2:
            result.correctness_score = score_parts[0] + score_parts[1]
    else:
        # No data available — neutral score
        result.correctness_score = 50.0

    return result


def _coverage_from_gfa(gfa_path: Path) -> CoverageResult:
    """Extract per-contig depth from GFA tags (HiMT method).

    Reads DP tags or calculates from RC/LN tags:
    S  contig1  ACGT...  dp:f:45.2  -> depth = 45.2
    S  contig2  ACGT...  RC:i:90400  LN:i:2000  -> depth = 90400/2000
    """
    result = CoverageResult()
    depths = []

    try:
        with open(gfa_path) as f:
            for line in f:
                if not line.startswith("S\t"):
                    continue
                parts = line.strip().split("\t")
                if len(parts) < 3:
                    continue

                depth = None
                for tag in parts[3:]:
                    if tag.startswith("dp:f:"):
                        depth = float(tag.split(":")[2])
                    elif tag.startswith("DP:f:"):
                        depth = float(tag.split(":")[2])

                if depth is not None:
                    depths.append(depth)
    except Exception as e:
        logger.debug(f"Failed to parse GFA: {e}")
        return result

    if not depths:
        return result

    import statistics
    result.mean_depth = statistics.mean(depths)
    result.median_depth = statistics.median(depths)
    result.std_depth = statistics.stdev(depths) if len(depths) > 1 else 0
    result.cv = result.std_depth / result.mean_depth if result.mean_depth > 0 else 0
    result.min_depth = int(min(depths))
    result.max_depth = int(max(depths))
    result.is_available = True

    # Check for anomalous contigs
    for i, d in enumerate(depths):
        if d < result.mean_depth * 0.2:
            result.low_coverage_regions.append((i, i))  # contig index
        elif d > result.mean_depth * 5:
            result.high_coverage_regions.append((i, i))

    result.depth_uniformity_score = _score_coverage(result.cv)
    return result


def _coverage_from_bam(bam_path: Path) -> CoverageResult:
    """Calculate coverage from BAM using samtools depth."""
    result = CoverageResult()

    samtools = shutil.which("samtools")
    if not samtools:
        return result

    proc = subprocess.run(
        [samtools, "depth", str(bam_path)],
        capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        return result

    depths = []
    for line in proc.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 3:
            try:
                depths.append(int(parts[2]))
            except ValueError:
                continue

    if not depths:
        return result

    import statistics
    result.mean_depth = statistics.mean(depths)
    result.median_depth = statistics.median(depths)
    result.std_depth = statistics.stdev(depths) if len(depths) > 1 else 0
    result.cv = result.std_depth / result.mean_depth if result.mean_depth > 0 else 0
    result.min_depth = min(depths)
    result.max_depth = max(depths)
    result.is_available = True

    # Find problematic regions
    low_thresh = result.mean_depth * 0.2
    high_thresh = result.mean_depth * 5
    zero_start = None
    low_start = None
    high_start = None

    for i, d in enumerate(depths):
        pos = i + 1
        if d == 0:
            if zero_start is None:
                zero_start = pos
        else:
            if zero_start is not None:
                result.zero_coverage_regions.append((zero_start, pos - 1))
                zero_start = None

        if d < low_thresh:
            if low_start is None:
                low_start = pos
        else:
            if low_start is not None:
                result.low_coverage_regions.append((low_start, pos - 1))
                low_start = None

        if d > high_thresh:
            if high_start is None:
                high_start = pos
        else:
            if high_start is not None:
                result.high_coverage_regions.append((high_start, pos - 1))
                high_start = None

    result.depth_uniformity_score = _score_coverage(result.cv)
    return result


def _coverage_from_reads(
    fasta_path: Path,
    reads_sr: Optional[list],
    reads_lr: Optional[str],
) -> CoverageResult:
    """Map reads and calculate coverage."""
    minimap2 = shutil.which("minimap2")
    samtools = shutil.which("samtools")
    if not minimap2 or not samtools:
        return CoverageResult()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        bam_out = tmp / "mapped.bam"

        # Map reads
        if reads_sr:
            cmd = [
                minimap2, "-ax", "sr", "-t", "4",
                str(fasta_path), *reads_sr,
            ]
        elif reads_lr:
            cmd = [
                minimap2, "-ax", "map-pb", "-t", "4",
                str(fasta_path), reads_lr,
            ]
        else:
            return CoverageResult()

        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=600)
            with open(tmp / "mapped.sam", "wb") as f:
                f.write(proc.stdout)

            subprocess.run(
                [samtools, "sort", "-o", str(bam_out), str(tmp / "mapped.sam")],
                capture_output=True, timeout=120,
            )
            subprocess.run(
                [samtools, "index", str(bam_out)],
                capture_output=True, timeout=60,
            )

            return _coverage_from_bam(bam_out)
        except (subprocess.TimeoutExpired, Exception) as e:
            logger.warning(f"Read mapping failed: {e}")
            return CoverageResult()


def _assess_base_accuracy(
    fasta_path: Path, reads_sr: list, min_depth: int
) -> BaseAccuracyResult:
    """Assess base-level accuracy using short reads."""
    result = BaseAccuracyResult()

    samtools = shutil.which("samtools")
    bcftools = shutil.which("bcftools")
    minimap2 = shutil.which("minimap2")

    if not all([samtools, bcftools, minimap2]):
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        bam_out = tmp / "mapped.bam"
        vcf_out = tmp / "variants.vcf"

        try:
            # Map
            proc = subprocess.run(
                [minimap2, "-ax", "sr", "-t", "4", str(fasta_path)] + reads_sr,
                capture_output=True, timeout=600,
            )
            with open(tmp / "mapped.sam", "wb") as f:
                f.write(proc.stdout)

            subprocess.run(
                [samtools, "sort", "-o", str(bam_out), str(tmp / "mapped.sam")],
                capture_output=True, timeout=120,
            )
            subprocess.run(
                [samtools, "index", str(bam_out)],
                capture_output=True, timeout=60,
            )

            # Call variants
            subprocess.run(
                [bcftools, "mpileup", "-f", str(fasta_path), str(bam_out),
                 "|", bcftools, "call", "-mv", "-o", str(vcf_out)],
                capture_output=True, timeout=300, shell=True,
            )

            if not vcf_out.exists():
                return result

            # Parse VCF
            snp_count = 0
            indel_count = 0
            total_bases = 0

            with open(vcf_out) as f:
                for line in f:
                    if line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) < 5:
                        continue
                    ref = parts[3]
                    alt = parts[4]
                    if len(ref) == 1 and len(alt) == 1:
                        snp_count += 1
                    else:
                        indel_count += 1

            # QV estimation
            total_bases = _count_fasta_bases(fasta_path)
            total_variants = snp_count + indel_count
            error_rate = total_variants / total_bases if total_bases > 0 else 1
            import math
            qv = -10 * math.log10(error_rate) if error_rate > 0 else 60

            result.total_bases = total_bases
            result.snp_count = snp_count
            result.indel_count = indel_count
            result.consistency_rate = 1 - error_rate
            result.qv = qv
            result.is_available = True

        except Exception as e:
            logger.warning(f"Base accuracy assessment failed: {e}")

    return result


def _count_fasta_bases(fasta_path: Path) -> int:
    """Count total bases in FASTA."""
    total = 0
    with open(fasta_path) as f:
        for line in f:
            if not line.startswith(">"):
                total += len(line.strip())
    return total


def _score_coverage(cv: float) -> float:
    """Score coverage uniformity from CV."""
    # CV < 0.2 = excellent, 0.2-0.5 = good, 0.5-1.0 = fair, >1.0 = poor
    if cv < 0.2:
        return 100
    elif cv < 0.5:
        return 90 - (cv - 0.2) / 0.3 * 20
    elif cv < 1.0:
        return 70 - (cv - 0.5) / 0.5 * 30
    else:
        return max(0, 40 - (cv - 1.0) * 20)
