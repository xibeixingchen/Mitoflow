"""Ka/Ks visualization using R (ggplot2 + eoffice).

Generates publication-quality plots in PNG, PDF, and PPTX formats.
PPTX output uses the eoffice R package's topptx() function.

Falls back to matplotlib (visualize.py) if R or required packages are unavailable.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .calculator import KaKsBatchResult

logger = logging.getLogger(__name__)


def check_r_kaks_available() -> bool:
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


def plot_kaks_with_r(
    results: list[KaKsBatchResult],
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
    width: float = 10.0,
    height: float = 7.0,
) -> dict[str, Path]:
    """Generate Ka/Ks plots using R (ggplot2 + eoffice).

    Outputs PNG, PDF, and PPTX for each of 5 plot types:
    kaks_barplot, kaks_boxplot, ka_vs_ks, selection_pie, kaks_dotplot

    Args:
        results: List of KaKsBatchResult from batch_kaks().
        output_dir: Output directory.
        prefix: File name prefix.
        dpi: Resolution for PNG.
        width: Figure width in inches.
        height: Figure height in inches.

    Returns:
        Dict mapping plot name to primary output path (PNG).

    Raises:
        RuntimeError: If R or required packages are unavailable.
    """
    rscript = _find_rscript()
    if not rscript:
        raise RuntimeError("Rscript not found in PATH")

    r_script = Path(__file__).parent / "kaks_plots.R"
    if not r_script.exists():
        raise RuntimeError(f"R wrapper not found: {r_script}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write results to a temporary TSV for R to read
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="mitoflow_kaks_", delete=False
    ) as tmp:
        tmp.write("gene\tcategory\tspecies_a\tspecies_b\tKa\tKs\tKa_Ks\tcodons\tidentity_pct\tmethod\tselection\n")
        for batch in results:
            for r in batch.results:
                ratio_str = f"{r.kaks_ratio:.4f}" if r.selection != "NA" else "NA"
                tmp.write(
                    f"{r.gene}\t{r.category}\t{r.species_a}\t{r.species_b}\t"
                    f"{r.ka:.6f}\t{r.ks:.6f}\t{ratio_str}\t"
                    f"{r.alignment_codons}\t{r.identity_pct:.1f}\t"
                    f"{r.method}\t{r.selection}\n"
                )
        tsv_path = tmp.name

    out_prefix = str(output_dir / prefix)

    cmd = [
        rscript, str(r_script),
        tsv_path, out_prefix,
        str(width), str(height), str(dpi),
    ]

    logger.info(f"Running R Ka/Ks visualization: {' '.join(cmd)}")

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
        # Clean up temp TSV
        Path(tsv_path).unlink(missing_ok=True)

    # Collect output files
    plot_names = ["kaks_barplot", "kaks_boxplot", "ka_vs_ks", "selection_pie", "kaks_dotplot"]
    files = {}
    for name in plot_names:
        png_path = output_dir / f"{prefix}_{name}.png"
        if png_path.exists():
            files[name] = png_path

    logger.info(f"R Ka/Ks plots written to {output_dir}")
    return files
