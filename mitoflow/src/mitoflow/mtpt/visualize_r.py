"""MTPT visualization using R (ggplot2 + eoffice).

Generates publication-quality plots in PNG, PDF, and PPTX formats.
Falls back to matplotlib (visualize.py) if R or required packages are unavailable.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def check_r_mtpt_available() -> bool:
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


def plot_mtpt_with_r(
    result,
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
    width: float = 10.0,
    height: float = 7.0,
) -> dict[str, Path]:
    """Generate MTPT plots using R (ggplot2 + eoffice).

    Outputs PNG, PDF, and PPTX for each of 4 plot types:
    mtpt_barplot, mtpt_identity, mtpt_mito_map, mtpt_gene_coverage

    Args:
        result: MTPTResult from detect_mtpt().
        output_dir: Output directory.
        prefix: File name prefix.
        dpi: Resolution for PNG.
        width: Figure width in inches.
        height: Figure height in inches.

    Returns:
        Dict mapping plot name to primary output path (PNG).
    """
    rscript = _find_rscript()
    if not rscript:
        raise RuntimeError("Rscript not found in PATH")

    r_script = Path(__file__).parent / "mtpt_plots.R"
    if not r_script.exists():
        raise RuntimeError(f"R wrapper not found: {r_script}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write MTPT results to a temporary TSV for R to read
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="mitoflow_mtpt_", delete=False
    ) as tmp:
        tmp.write("MitoStart\tMitoEnd\tCpStart\tCpEnd\tIdentity\tLength\tCategory\tCpGenes\n")
        for r in result.regions:
            genes = ",".join(r.cp_genes_covered) if r.cp_genes_covered else "none"
            tmp.write(
                f"{r.mito_start}\t{r.mito_end}\t{r.cp_start}\t{r.cp_end}\t"
                f"{r.identity:.1f}\t{r.length}\t{r.category}\t{genes}\n"
            )
        tsv_path = tmp.name

    out_prefix = str(output_dir / prefix)

    cmd = [
        rscript, str(r_script),
        tsv_path, out_prefix,
        str(width), str(height), str(dpi),
    ]

    logger.info(f"Running R MTPT visualization: {' '.join(cmd)}")

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
    plot_names = ["mtpt_barplot", "mtpt_identity", "mtpt_mito_map", "mtpt_gene_coverage"]
    files = {}
    for name in plot_names:
        png_path = output_dir / f"{prefix}_{name}.png"
        if png_path.exists():
            files[name] = png_path

    logger.info(f"R MTPT plots written to {output_dir}")
    return files
