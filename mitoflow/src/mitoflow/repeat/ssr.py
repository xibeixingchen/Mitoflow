"""Simple Sequence Repeat (SSR / microsatellite) detection.

Wraps MISA (MIcroSAtellite identification tool) via subprocess.
Falls back to a pure-Python regex scanner if MISA is unavailable.

MISA motif thresholds (default for plant mitochondria):
  mono: 10, di: 7, tri: 6, tetra: 5, penta: 5, hexa: 5
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Default minimum repeat unit counts (plant mitochondria)
DEFAULT_MOTIF_THRESHOLDS = {
    1: 10,  # mono-nucleotide
    2: 7,   # di-
    3: 6,   # tri-
    4: 5,   # tetra-
    5: 5,   # penta-
    6: 5,   # hexa-
}


@dataclass
class SSRRecord:
    """A single SSR locus."""
    sequence_id: str
    start: int          # 1-based
    end: int            # inclusive
    motif: str          # e.g. "AT"
    repeat_count: int
    length: int         # bp
    category: str       # mono/di/tri/tetra/penta/hexa

    def to_bed_line(self) -> str:
        return f"{self.sequence_id}\t{self.start - 1}\t{self.end}\t{self.category}_{self.motif}\t{self.repeat_count}\t+"

    def to_gff_line(self) -> str:
        attrs = f"ID=ssr_{self.start};motif={self.motif};repeats={self.repeat_count};category={self.category}"
        return f"{self.sequence_id}\tMitoFlow\tSSR\t{self.start}\t{self.end}\t.\t+\t.\t{attrs}"


@dataclass
class SSRResult:
    """SSR detection result."""
    ssrs: list[SSRRecord] = field(default_factory=list)
    genome_length: int = 0
    tool_used: str = "regex"

    @property
    def total_count(self) -> int:
        return len(self.ssrs)

    @property
    def density_per_kb(self) -> float:
        return self.total_count / (self.genome_length / 1000) if self.genome_length > 0 else 0.0

    @property
    def total_ssr_bp(self) -> int:
        return sum(s.length for s in self.ssrs)

    @property
    def coverage_pct(self) -> float:
        return self.total_ssr_bp / self.genome_length * 100 if self.genome_length > 0 else 0.0

    def by_category(self) -> dict[str, list[SSRRecord]]:
        cats = {}
        for s in self.ssrs:
            cats.setdefault(s.category, []).append(s)
        return cats

    def summary(self) -> str:
        lines = [
            f"SSR Detection ({self.tool_used})",
            f"  Total SSRs: {self.total_count}",
            f"  Density: {self.density_per_kb:.2f} per kb",
            f"  Coverage: {self.coverage_pct:.3f}%",
            f"  Total SSR bp: {self.total_ssr_bp}",
        ]
        for cat in ["mono", "di", "tri", "tetra", "penta", "hexa"]:
            ssrs = [s for s in self.ssrs if s.category == cat]
            if ssrs:
                lines.append(f"  {cat}: {len(ssrs)}")
        return "\n".join(lines)


def detect_ssr(
    fasta_path: Path,
    output_dir: Path,
    motif_thresholds: dict[int, int] | None = None,
) -> SSRResult:
    """Detect SSRs in a mitochondrial genome.

    Tries MISA first, falls back to pure-Python regex scanner.

    Args:
        fasta_path: Input genome FASTA
        output_dir: Directory for output files
        motif_thresholds: Min repeat counts per motif length {1:10, 2:7, ...}

    Returns:
        SSRResult with detected SSRs
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    thresholds = motif_thresholds or DEFAULT_MOTIF_THRESHOLDS

    # Try MISA
    if shutil.which("misa") or shutil.which("perl"):
        result = _run_misa(fasta_path, output_dir, thresholds)
        if result is not None:
            return result

    # Fallback: pure Python
    logger.info("MISA not found, using built-in regex SSR scanner")
    return _detect_ssr_python(fasta_path, thresholds)


def _detect_ssr_python(
    fasta_path: Path,
    thresholds: dict[int, int],
) -> SSRResult:
    """Pure-Python SSR detection using regex."""
    from Bio import SeqIO

    ssrs = []
    genome_length = 0

    for record in SeqIO.parse(str(fasta_path), "fasta"):
        seq = str(record.seq).upper()
        genome_length += len(seq)
        seen_positions = set()

        for motif_len, min_repeats in thresholds.items():
            # Build regex for this motif length
            # We scan all possible motifs of this length
            for i in range(len(seq) - motif_len):
                if i in seen_positions:
                    continue
                motif = seq[i:i + motif_len]
                if 'N' in motif:
                    continue

                # Count consecutive repeats
                count = 1
                pos = i + motif_len
                while pos + motif_len <= len(seq) and seq[pos:pos + motif_len] == motif:
                    count += 1
                    pos += motif_len

                if count >= min_repeats:
                    ssr = SSRRecord(
                        sequence_id=record.id,
                        start=i + 1,
                        end=pos,
                        motif=motif,
                        repeat_count=count,
                        length=pos - i,
                        category=_motif_category(motif_len),
                    )
                    ssrs.append(ssr)
                    # Mark positions to avoid double-counting
                    for p in range(i, pos):
                        seen_positions.add(p)

    return SSRResult(ssrs=ssrs, genome_length=genome_length, tool_used="regex")


def _run_misa(
    fasta_path: Path,
    output_dir: Path,
    thresholds: dict[int, int],
) -> SSRResult | None:
    """Run MISA via subprocess (requires Perl)."""
    perl = shutil.which("perl")
    misa_script = shutil.which("misa")
    if not perl:
        return None

    # Try to find misa.pl
    if not misa_script:
        # Check common locations
        for p in ["/usr/local/bin/misa.pl", "/usr/bin/misa.pl",
                   str(Path.home() / "bin/misa.pl")]:
            if Path(p).exists():
                misa_script = p
                break

    if not misa_script:
        return None

    # Write MISA settings file
    settings_file = output_dir / "misa.ini"
    settings_lines = [
        f"definition(unit_size,min_repeats): {' '.join(f'{k} {v}' for k, v in sorted(thresholds.items()))}",
        "definition(maximal_number_of_bases_between_SSRs_to_form_compound_SSR): 100",
    ]
    settings_file.write_text("\n".join(settings_lines))

    try:
        cmd = [perl, str(misa_script), str(fasta_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                                cwd=str(output_dir))
        if result.returncode != 0:
            logger.warning(f"MISA failed: {result.stderr[:200]}")
            return None

        # Parse MISA output
        output_file = output_dir / f"{fasta_path.stem}.misa"
        if not output_file.exists():
            output_file = output_dir / f"{fasta_path.stem}.statistics"
            if not output_file.exists():
                return None

        return _parse_misa_output(output_file, fasta_path)

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"MISA execution failed: {e}")
        return None


def _parse_misa_output(output_file: Path, fasta_path: Path) -> SSRResult:
    """Parse MISA output file."""
    from Bio import SeqIO
    genome_length = sum(len(r.seq) for r in SeqIO.parse(str(fasta_path), "fasta"))

    ssrs = []
    for line in output_file.read_text().strip().split("\n"):
        if line.startswith("#") or line.startswith("ID") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        try:
            ssr = SSRRecord(
                sequence_id=parts[0],
                start=int(parts[3]),
                end=int(parts[4]),
                motif=parts[2],
                repeat_count=int(parts[5]),
                length=int(parts[6]),
                category=parts[1],
            )
            ssrs.append(ssr)
        except (ValueError, IndexError):
            continue

    return SSRResult(ssrs=ssrs, genome_length=genome_length, tool_used="MISA")


def write_ssr_output(result: SSRResult, output_dir: Path, name: str) -> dict[str, Path]:
    """Write SSR results to files (GFF, BED, TSV)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    # TSV
    tsv_path = output_dir / f"{name}_ssr.tsv"
    with open(tsv_path, "w") as f:
        f.write("SeqID\tStart\tEnd\tMotif\tRepeats\tLength\tCategory\n")
        for s in result.ssrs:
            f.write(f"{s.sequence_id}\t{s.start}\t{s.end}\t{s.motif}\t{s.repeat_count}\t{s.length}\t{s.category}\n")
    files["tsv"] = tsv_path

    # GFF
    gff_path = output_dir / f"{name}_ssr.gff"
    with open(gff_path, "w") as f:
        f.write("##gff-version 3\n")
        for s in result.ssrs:
            f.write(s.to_gff_line() + "\n")
    files["gff"] = gff_path

    # BED
    bed_path = output_dir / f"{name}_ssr.bed"
    with open(bed_path, "w") as f:
        for s in result.ssrs:
            f.write(s.to_bed_line() + "\n")
    files["bed"] = bed_path

    return files


def _motif_category(motif_len: int) -> str:
    return {1: "mono", 2: "di", 3: "tri", 4: "tetra", 5: "penta", 6: "hexa"}.get(
        motif_len, f"unit{motif_len}"
    )
