"""Multiconf visualization using R (ggplot2 + eoffice).

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
    from .repeat_mediated import MulticonfResult

logger = logging.getLogger(__name__)


def check_r_multiconf_available() -> bool:
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


def plot_multiconf_with_r(
    result: "MulticonfResult",
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
    width: float = 10.0,
    height: float = 7.0,
    genome_length: int = 0,
) -> dict[str, Path]:
    """Generate Multiconf plots using R (ggplot2 + eoffice).

    Outputs PNG, PDF, and PPTX for each of 4 plot types:
    multiconf_repeat_map, multiconf_config_diagram,
    multiconf_recomb_summary, multiconf_type_dist

    Args:
        result: MulticonfResult from analysis.
        output_dir: Output directory.
        prefix: File name prefix.
        dpi: Resolution for PNG.
        width: Figure width in inches.
        height: Figure height in inches.
        genome_length: Total genome length in bp.

    Returns:
        Dict mapping plot name to primary output path (PNG).
    """
    rscript = _find_rscript()
    if not rscript:
        raise RuntimeError("Rscript not found in PATH")

    r_script = Path(__file__).parent / "multiconf_plots.R"
    if not r_script.exists():
        raise RuntimeError(f"R wrapper not found: {r_script}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write repeat pairs to temp TSV
    reps_tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="mitoflow_reps_", delete=False
    )
    reps_tmp.write(
        "repeat_id\trepeat_type\tcopy1_start\tcopy1_end\tcopy2_start\tcopy2_end\t"
        "length\tidentity\trecombination_active\trecombination_ratio\n"
    )
    for rp in result.repeat_pairs:
        active = "TRUE" if rp.recombination_active else (
            "FALSE" if rp.recombination_active is False else "NA"
        )
        ratio = f"{rp.recombination_ratio:.4f}" if rp.recombination_ratio is not None else "NA"
        reps_tmp.write(
            f"{rp.id}\t{rp.repeat_type}\t{rp.copy1_start}\t{rp.copy1_end}\t"
            f"{rp.copy2_start}\t{rp.copy2_end}\t{rp.length}\t{rp.identity:.1f}\t"
            f"{active}\t{ratio}\n"
        )
    reps_tmp.close()

    # Write subgenomic configs to temp TSV
    conf_tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="mitoflow_conf_", delete=False
    )
    conf_tmp.write("config_name\tsize\tgene_count\tis_major\n")
    for sg in result.subgenomic_circles:
        is_major = "TRUE" if sg.is_major else "FALSE"
        gene_count = len(sg.genes) if sg.genes else 0
        conf_tmp.write(
            f"{sg.configuration}\t{sg.size}\t{gene_count}\t{is_major}\n"
        )
    conf_tmp.close()

    out_prefix = str(output_dir / prefix)

    cmd = [
        rscript, str(r_script),
        reps_tmp.name, out_prefix, conf_tmp.name,
        str(genome_length), str(width), str(height), str(dpi),
    ]

    logger.info(f"Running R Multiconf visualization: {' '.join(cmd)}")

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
        Path(reps_tmp.name).unlink(missing_ok=True)
        Path(conf_tmp.name).unlink(missing_ok=True)

    # Collect output files
    plot_names = [
        "multiconf_repeat_map", "multiconf_config_diagram",
        "multiconf_recomb_summary", "multiconf_type_dist",
    ]
    files = {}
    for name in plot_names:
        png_path = output_dir / f"{prefix}_{name}.png"
        if png_path.exists():
            files[name] = png_path

    logger.info(f"R Multiconf plots written to {output_dir}")
    return files
