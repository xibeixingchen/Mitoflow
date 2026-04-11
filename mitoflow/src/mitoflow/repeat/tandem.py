"""Tandem Repeat detection using TRF (Tandem Repeats Finder).

Wraps TRF via subprocess. Falls back to a simple Python tandem repeat
scanner if TRF is not installed.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# TRF default parameters for plant mitochondria
TRF_PARAMS = "2 7 7 80 10 50 2000 -d -h"


@dataclass
class TandemRepeat:
    """A single tandem repeat locus."""
    sequence_id: str
    start: int          # 1-based
    end: int            # inclusive
    period_size: int    # consensus repeat unit length
    copy_number: float
    consensus: str      # repeat unit consensus
    percent_matches: float
    percent_indels: float
    score: int
    length: int

    def to_gff_line(self) -> str:
        attrs = (
            f"ID=tandem_{self.start};period={self.period_size};"
            f"copies={self.copy_number:.1f};consensus={self.consensus};"
            f"score={self.score}"
        )
        return (
            f"{self.sequence_id}\tTRF\ttandem_repeat\t{self.start}\t{self.end}\t"
            f"{self.score}\t+\t.\t{attrs}"
        )


@dataclass
class TandemRepeatResult:
    """Tandem repeat detection result."""
    repeats: list[TandemRepeat] = field(default_factory=list)
    genome_length: int = 0
    tool_used: str = "regex"

    @property
    def total_count(self) -> int:
        return len(self.repeats)

    @property
    def total_bp(self) -> int:
        return sum(r.length for r in self.repeats)

    @property
    def coverage_pct(self) -> float:
        return self.total_bp / self.genome_length * 100 if self.genome_length > 0 else 0.0

    def by_period_range(self) -> dict[str, list[TandemRepeat]]:
        bins = {"2-6bp": [], "7-15bp": [], "16-30bp": [], "31-100bp": [], ">100bp": []}
        for r in self.repeats:
            p = r.period_size
            if p <= 6:
                bins["2-6bp"].append(r)
            elif p <= 15:
                bins["7-15bp"].append(r)
            elif p <= 30:
                bins["16-30bp"].append(r)
            elif p <= 100:
                bins["31-100bp"].append(r)
            else:
                bins[">100bp"].append(r)
        return bins

    def summary(self) -> str:
        lines = [
            f"Tandem Repeat Detection ({self.tool_used})",
            f"  Total repeats: {self.total_count}",
            f"  Total bp: {self.total_bp:,}",
            f"  Coverage: {self.coverage_pct:.3f}%",
        ]
        for label, reps in self.by_period_range().items():
            if reps:
                lines.append(f"  Period {label}: {len(reps)} loci")
        return "\n".join(lines)


def detect_tandem_repeats(
    fasta_path: Path,
    output_dir: Path,
    params: str = TRF_PARAMS,
) -> TandemRepeatResult:
    """Detect tandem repeats.

    Args:
        fasta_path: Input genome FASTA
        output_dir: Output directory
        params: TRF parameters string

    Returns:
        TandemRepeatResult
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    trf = shutil.which("trf")
    if trf:
        result = _run_trf(fasta_path, output_dir, trf, params)
        if result is not None:
            return result

    logger.info("TRF not found, using built-in tandem repeat scanner")
    return _detect_tandem_python(fasta_path)


def _detect_tandem_python(fasta_path: Path) -> TandemRepeatResult:
    """Simple Python tandem repeat scanner (2-50bp period)."""
    from Bio import SeqIO

    repeats = []
    genome_length = 0

    for record in SeqIO.parse(str(fasta_path), "fasta"):
        seq = str(record.seq).upper()
        genome_length += len(seq)

        for period in range(2, 51):
            for i in range(len(seq) - period * 2):
                unit = seq[i:i + period]
                if "N" in unit:
                    continue

                count = 1
                pos = i + period
                while pos + period <= len(seq) and seq[pos:pos + period] == unit:
                    count += 1
                    pos += period

                if count >= 3:
                    length = pos - i
                    repeats.append(TandemRepeat(
                        sequence_id=record.id,
                        start=i + 1,
                        end=pos,
                        period_size=period,
                        copy_number=float(count),
                        consensus=unit,
                        percent_matches=100.0,
                        percent_indels=0.0,
                        score=count * period,
                        length=length,
                    ))
                    # Skip past this repeat to avoid sub-repeats
                    break  # Only take longest period at each position

    # Remove nested/overlapping (keep highest score per position)
    repeats = _remove_overlaps(repeats)

    return TandemRepeatResult(repeats=repeats, genome_length=genome_length, tool_used="regex")


def _remove_overlaps(repeats: list[TandemRepeat]) -> list[TandemRepeat]:
    """Remove overlapping tandem repeat calls, keeping highest score."""
    if not repeats:
        return []
    repeats.sort(key=lambda r: r.score, reverse=True)
    kept = []
    for r in repeats:
        if not any(r.start <= k.end and r.end >= k.start for k in kept):
            kept.append(r)
    return sorted(kept, key=lambda r: r.start)


def _run_trf(
    fasta_path: Path, output_dir: Path, trf_path: str, params: str,
) -> TandemRepeatResult | None:
    """Run TRF via subprocess."""
    try:
        cmd = [trf_path, str(fasta_path)] + params.split()
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            cwd=str(output_dir),
        )
        if result.returncode not in (0, 1):
            logger.warning(f"TRF failed: {result.stderr[:200]}")
            return None

        # Find TRF output file (*.dat)
        dat_files = list(output_dir.glob("*.dat"))
        if not dat_files:
            dat_files = list(output_dir.glob(f"{fasta_path.stem}.*.dat"))
        if not dat_files:
            return None

        return _parse_trf_output(dat_files[0], fasta_path)

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"TRF execution failed: {e}")
        return None


def _parse_trf_output(dat_file: Path, fasta_path: Path) -> TandemRepeatResult:
    """Parse TRF .dat output file."""
    from Bio import SeqIO
    genome_length = sum(len(r.seq) for r in SeqIO.parse(str(fasta_path), "fasta"))

    repeats = []
    seq_id = ""
    with open(dat_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("Sequence:"):
                seq_id = line.replace("Sequence:", "").strip()
                continue
            if not line or line.startswith("@"):
                continue

            parts = line.split()
            if len(parts) < 15:
                continue
            try:
                repeats.append(TandemRepeat(
                    sequence_id=seq_id,
                    start=int(parts[0]),
                    end=int(parts[1]),
                    period_size=int(parts[2]),
                    copy_number=float(parts[3]),
                    consensus=parts[13] if len(parts) > 13 else "",
                    percent_matches=float(parts[4]),
                    percent_indels=float(parts[5]),
                    score=int(parts[7]),
                    length=int(parts[8]),
                ))
            except (ValueError, IndexError):
                continue

    return TandemRepeatResult(repeats=repeats, genome_length=genome_length, tool_used="TRF")


def write_tandem_output(result: TandemRepeatResult, output_dir: Path, name: str) -> dict[str, Path]:
    """Write tandem repeat results to files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    tsv_path = output_dir / f"{name}_tandem.tsv"
    with open(tsv_path, "w") as f:
        f.write("SeqID\tStart\tEnd\tPeriod\tCopies\tScore\tConsensus\tLength\n")
        for r in result.repeats:
            f.write(
                f"{r.sequence_id}\t{r.start}\t{r.end}\t{r.period_size}\t"
                f"{r.copy_number:.1f}\t{r.score}\t{r.consensus}\t{r.length}\n"
            )
    files["tsv"] = tsv_path

    gff_path = output_dir / f"{name}_tandem.gff"
    with open(gff_path, "w") as f:
        f.write("##gff-version 3\n")
        for r in result.repeats:
            f.write(r.to_gff_line() + "\n")
    files["gff"] = gff_path

    return files
