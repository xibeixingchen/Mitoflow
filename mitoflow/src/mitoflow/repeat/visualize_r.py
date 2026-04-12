"""Repeat visualization using R (ggplot2 + eoffice).

Generates publication-quality plots in PNG, PDF, and PPTX formats.

Falls back to matplotlib (visualize.py) if R or required packages are unavailable.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .ssr import SSRResult
    from .tandem import TandemRepeatResult
    from .long_repeat import LongRepeatResult

logger = logging.getLogger(__name__)


def check_r_repeat_available() -> bool:
    """Check if R with ggplot2 and eoffice is available."""
    rscript = _find_rscript()
    if not rscript:
        return False

    try:
        result = subprocess.run(
            [rscript, "-e", "require(ggplot2) && require(eoffice)"],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _find_rscript() -> Optional[str]:
    """Find Rscript binary."""
    import shutil
    return shutil.which("Rscript")


def plot_repeat_with_r(
    ssr_result: "SSRResult",
    tandem_result: "TandemRepeatResult",
    long_result: "LongRepeatResult",
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
    width: float = 10.0,
    height: float = 7.0,
    genome_length: int = 0,
) -> dict[str, Path]:
    """Generate repeat plots using R (ggplot2 + eoffice).

    Outputs PNG, PDF, and PPTX for each of 5 plot types:
    repeat_ssr_dist, repeat_ssr_motif, repeat_tandem_period,
    repeat_long_map, repeat_long_type

    Args:
        ssr_result: SSRResult from detect_ssr().
        tandem_result: TandemRepeatResult from detect_tandem_repeats().
        long_result: LongRepeatResult from detect_long_repeats().
        output_dir: Output directory.
        prefix: File name prefix.
        dpi: Resolution for PNG.
        width: Figure width in inches.
        height: Figure height in inches.
        genome_length: Total genome length in bp (for long repeat map).

    Returns:
        Dict mapping plot name to primary output path (PNG).
    """
    rscript = _find_rscript()
    if not rscript:
        raise RuntimeError("Rscript not found in PATH")

    r_script = Path(__file__).parent / "repeat_plots.R"
    if not r_script.exists():
        raise RuntimeError(f"R wrapper not found: {r_script}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write SSR results to temp TSV
    ssr_path = None
    if ssr_result and ssr_result.ssrs:
        ssr_tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", prefix="mitoflow_ssr_", delete=False
        )
        ssr_tmp.write("sequence_id\tstart\tend\tmotif\trepeat_count\tlength\tcategory\n")
        for s in ssr_result.ssrs:
            ssr_tmp.write(
                f"{s.sequence_id}\t{s.start}\t{s.end}\t{s.motif}\t"
                f"{s.repeat_count}\t{s.length}\t{s.category}\n"
            )
        ssr_tmp.close()
        ssr_path = ssr_tmp.name
    else:
        # Write empty file so R can still check it
        ssr_tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", prefix="mitoflow_ssr_", delete=False
        )
        ssr_tmp.write("sequence_id\tstart\tend\tmotif\trepeat_count\tlength\tcategory\n")
        ssr_tmp.close()
        ssr_path = ssr_tmp.name

    # Write tandem repeat results to temp TSV
    tandem_path = None
    if tandem_result and tandem_result.repeats:
        tandem_tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", prefix="mitoflow_tandem_", delete=False
        )
        tandem_tmp.write("sequence_id\tstart\tend\tperiod_size\tcopy_number\tconsensus\tpercent_matches\tscore\tlength\n")
        for r in tandem_result.repeats:
            tandem_tmp.write(
                f"{r.sequence_id}\t{r.start}\t{r.end}\t{r.period_size}\t"
                f"{r.copy_number:.1f}\t{r.consensus}\t{r.percent_matches:.1f}\t"
                f"{r.score}\t{r.length}\n"
            )
        tandem_tmp.close()
        tandem_path = tandem_tmp.name
    else:
        tandem_tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", prefix="mitoflow_tandem_", delete=False
        )
        tandem_tmp.write("sequence_id\tstart\tend\tperiod_size\tcopy_number\tconsensus\tpercent_matches\tscore\tlength\n")
        tandem_tmp.close()
        tandem_path = tandem_tmp.name

    # Write long repeat results to temp TSV
    long_path = None
    if long_result and long_result.repeat_pairs:
        long_tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", prefix="mitoflow_long_", delete=False
        )
        long_tmp.write("repeat_id\ttype\tcopy1_start\tcopy1_end\tcopy2_start\tcopy2_end\tlength\tidentity\torientation\n")
        for r in long_result.repeat_pairs:
            long_tmp.write(
                f"{r.repeat_id}\t{r.type}\t{r.copy1_start}\t{r.copy1_end}\t"
                f"{r.copy2_start}\t{r.copy2_end}\t{r.length}\t{r.identity:.1f}\t{r.orientation}\n"
            )
        long_tmp.close()
        long_path = long_tmp.name
    else:
        long_tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", prefix="mitoflow_long_", delete=False
        )
        long_tmp.write("repeat_id\ttype\tcopy1_start\tcopy1_end\tcopy2_start\tcopy2_end\tlength\tidentity\torientation\n")
        long_tmp.close()
        long_path = long_tmp.name

    out_prefix = str(output_dir / prefix)

    cmd = [
        rscript, str(r_script),
        ssr_path, tandem_path, long_path, out_prefix,
        str(genome_length), str(width), str(height), str(dpi),
    ]

    logger.info(f"Running R Repeat visualization: {' '.join(cmd)}")

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
        if proc.stdout:
            for line in proc.stdout.strip().split("\n"):
                logger.info(f"[R] {line}")
        if proc.returncode != 0:
            logger.warning(f"R visualization failed (exit {proc.returncode}): {proc.stderr}")
            raise RuntimeError(f"R visualization failed: {proc.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("R visualization timed out (300s)")
    finally:
        Path(ssr_path).unlink(missing_ok=True)
        Path(tandem_path).unlink(missing_ok=True)
        Path(long_path).unlink(missing_ok=True)

    # Collect output files
    plot_names = [
        "repeat_ssr_dist", "repeat_ssr_motif", "repeat_tandem_period",
        "repeat_long_map", "repeat_long_type",
    ]
    files = {}
    for name in plot_names:
        png_path = output_dir / f"{prefix}_{name}.png"
        if png_path.exists():
            files[name] = png_path

    logger.info(f"R Repeat plots written to {output_dir}")
    return files
