"""CMS visualization using R (ggplot2 + eoffice).

Generates publication-quality plots in PNG, PDF, and PPTX formats.

Falls back to matplotlib (visualize.py) if R or required packages are unavailable.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .predictor import CMSResult

logger = logging.getLogger(__name__)


def check_r_cms_available() -> bool:
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


def plot_cms_with_r(
    result: "CMSResult",
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
    width: float = 10.0,
    height: float = 7.0,
    genome_length: int = 0,
) -> dict[str, Path]:
    """Generate CMS plots using R (ggplot2 + eoffice).

    Outputs PNG, PDF, and PPTX for each of 4 plot types:
    cms_scores, cms_heatmap, cms_genome_context, cms_confidence

    Args:
        result: CMSResult from predict_cms().
        output_dir: Output directory.
        prefix: File name prefix.
        dpi: Resolution for PNG.
        width: Figure width in inches.
        height: Figure height in inches.
        genome_length: Total genome length in bp (needed for genome context plot).

    Returns:
        Dict mapping plot name to primary output path (PNG).
    """
    rscript = _find_rscript()
    if not rscript:
        raise RuntimeError("Rscript not found in PATH")

    r_script = Path(__file__).parent / "cms_plots.R"
    if not r_script.exists():
        raise RuntimeError(f"R wrapper not found: {r_script}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write CMS results to a temporary TSV for R to read
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="mitoflow_cms_", delete=False
    ) as tmp:
        tmp.write("orf_id\tstart\tend\tlength_aa\tchimera_score\ttm_score\thomolog_score\tcontext_score\tlength_score\ttotal_score\tconfidence\tn_tm_domains\n")
        for c in result.candidates:
            tmp.write(
                f"{c.orf_id}\t{c.start}\t{c.end}\t{c.length_aa}\t"
                f"{c.chimera_score}\t{c.tm_score}\t{c.homolog_score}\t"
                f"{c.context_score}\t{c.length_score}\t{c.total_score:.1f}\t"
                f"{c.confidence}\t{c.n_tm_domains}\n"
            )
        tsv_path = tmp.name

    out_prefix = str(output_dir / prefix)

    cmd = [
        rscript, str(r_script),
        tsv_path, out_prefix, str(genome_length),
        str(width), str(height), str(dpi),
    ]

    logger.info(f"Running R CMS visualization: {' '.join(cmd)}")

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
        Path(tsv_path).unlink(missing_ok=True)

    # Collect output files
    plot_names = ["cms_scores", "cms_heatmap", "cms_genome_context", "cms_confidence"]
    files = {}
    for name in plot_names:
        png_path = output_dir / f"{prefix}_{name}.png"
        if png_path.exists():
            files[name] = png_path

    logger.info(f"R CMS plots written to {output_dir}")
    return files
