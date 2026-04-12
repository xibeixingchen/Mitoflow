"""RNA editing visualization using R (ggplot2 + eoffice).

Generates publication-quality plots in PNG, PDF, and PPTX formats.
PPTX output uses the eoffice R package's topptx() function.

Falls back to matplotlib if R or required packages are unavailable.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .predictor import EditingSite

logger = logging.getLogger(__name__)


def check_r_rnaedit_available() -> bool:
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


def plot_rnaedit_with_r(
    editing_sites: list[EditingSite],
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
    width: float = 10.0,
    height: float = 7.0,
) -> dict[str, Path]:
    """Generate RNA editing plots using R (ggplot2 + eoffice).

    Outputs PNG, PDF, and PPTX for each of 3 plot types:
    editing_per_gene, editing_type_pie, codon_position

    Args:
        editing_sites: List of EditingSite predictions.
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

    r_script = Path(__file__).parent / "rnaedit_plots.R"
    if not r_script.exists():
        raise RuntimeError(f"R wrapper not found: {r_script}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write editing sites to a temporary TSV for R to read
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="mitoflow_rnaedit_", delete=False
    ) as tmp:
        tmp.write("gene\tcodon_position\tediting_type\toriginal_codon\tedited_codon\thas_start\thas_stop\n")
        for s in editing_sites:
            editing_type = "synonymous" if s.is_synonymous else "nonsynonymous"
            has_start = getattr(s, 'is_start_codon_creation', False)
            has_stop = getattr(s, 'is_stop_codon_removal', False)
            tmp.write(
                f"{s.gene}\t{s.codon_position}\t{editing_type}\t"
                f"{s.original_codon}\t{s.edited_codon}\t{has_start}\t{has_stop}\n"
            )
        tsv_path = tmp.name

    out_prefix = str(output_dir / prefix)

    cmd = [
        rscript, str(r_script),
        tsv_path, out_prefix,
        str(width), str(height), str(dpi),
    ]

    logger.info(f"Running R RNA editing visualization: {' '.join(cmd)}")

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
    plot_names = ["editing_per_gene", "editing_type_pie", "codon_position"]
    files = {}
    for name in plot_names:
        png_path = output_dir / f"{prefix}_{name}.png"
        if png_path.exists():
            files[name] = png_path

    logger.info(f"R RNA editing plots written to {output_dir}")
    return files
