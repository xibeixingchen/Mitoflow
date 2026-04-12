"""Codon usage visualization using R (ggplot2 + eoffice).

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

logger = logging.getLogger(__name__)


def check_r_codon_available() -> bool:
    """Check if R with ggplot2, gridExtra, and eoffice is available."""
    rscript = _find_rscript()
    if not rscript:
        return False

    try:
        result = subprocess.run(
            [rscript, "-e", "require(ggplot2) && require(gridExtra) && require(eoffice)"],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _find_rscript() -> Optional[str]:
    """Find Rscript binary."""
    import shutil
    return shutil.which("Rscript")


def plot_codon_with_r(
    result,
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
    width: float = 10.0,
    height: float = 7.0,
) -> dict[str, Path]:
    """Generate codon usage plots using R (ggplot2 + eoffice).

    Outputs PNG, PDF, and PPTX for each of 7 plot types:
    rscu_heatmap, enc_gc3s, enc_gc3s_enhanced, codon_bar, aa_freq, pr2_bias, neutrality

    Args:
        result: CodonUsageResult from analyze_codon_usage().
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
    from .analysis import CODON_TABLE

    rscript = _find_rscript()
    if not rscript:
        raise RuntimeError("Rscript not found in PATH")

    r_script = Path(__file__).parent / "codon_plots.R"
    if not r_script.exists():
        raise RuntimeError(f"R wrapper not found: {r_script}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write 4 temporary TSV files for R

    # 1. Gene-level data: gene, enc, gc3s, gc12, a3, t3, g3, c3
    gene_tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="mitoflow_codon_gene_", delete=False
    )
    gene_tmp.write("gene\tenc\tgc3s\tgc12\ta3\tt3\tg3\tc3\n")
    for gene in result.per_gene_enc:
        enc = result.per_gene_enc.get(gene, 0)
        gc3s = result.per_gene_gc3s.get(gene, 0)
        gc12 = result.per_gene_gc12.get(gene, 0)
        pr2 = result.per_gene_pr2.get(gene, {})
        a3 = pr2.get("A", 0)
        t3 = pr2.get("T", 0)
        g3 = pr2.get("G", 0)
        c3 = pr2.get("C", 0)
        gene_tmp.write(f"{gene}\t{enc}\t{gc3s}\t{gc12}\t{a3}\t{t3}\t{g3}\t{c3}\n")
    gene_tmp.close()

    # 2. RSCU data: gene, codon, rscu
    rscu_tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="mitoflow_codon_rscu_", delete=False
    )
    rscu_tmp.write("gene\tcodon\trscu\n")
    for gene, codon_rscu in result.per_gene_rscu.items():
        for codon, val in codon_rscu.items():
            rscu_tmp.write(f"{gene}\t{codon}\t{val}\n")
    rscu_tmp.close()

    # 3. Codon-level data: codon, aa, count, rscu
    codon_tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="mitoflow_codon_codon_", delete=False
    )
    codon_tmp.write("codon\taa\tcount\trscu\n")
    for codon, count in result.overall_codon_count.items():
        aa = CODON_TABLE.get(codon, "?")
        rscu_val = result.overall_rscu.get(codon, 0)
        codon_tmp.write(f"{codon}\t{aa}\t{count}\t{rscu_val}\n")
    codon_tmp.close()

    # 4. AA frequency data: aa, frequency
    aa_tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="mitoflow_codon_aa_", delete=False
    )
    aa_tmp.write("aa\tfrequency\n")
    if result.overall_aa_freq:
        total = sum(result.overall_aa_freq.values())
        sorted_aa = sorted(result.overall_aa_freq.keys(),
                          key=lambda a: result.overall_aa_freq[a], reverse=True)
        for aa in sorted_aa:
            freq = result.overall_aa_freq[aa] / total * 100
            aa_tmp.write(f"{aa}\t{freq:.2f}\n")
    aa_tmp.close()

    out_prefix = str(output_dir / prefix)

    cmd = [
        rscript, str(r_script),
        gene_tmp.name, rscu_tmp.name, codon_tmp.name, aa_tmp.name,
        out_prefix,
        str(width), str(height), str(dpi),
    ]

    logger.info(f"Running R Codon visualization: {' '.join(cmd)}")

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
        Path(gene_tmp.name).unlink(missing_ok=True)
        Path(rscu_tmp.name).unlink(missing_ok=True)
        Path(codon_tmp.name).unlink(missing_ok=True)
        Path(aa_tmp.name).unlink(missing_ok=True)

    # Collect output files
    plot_names = [
        "rscu_heatmap", "enc_gc3s", "enc_gc3s_enhanced",
        "codon_bar", "aa_freq", "pr2_bias", "neutrality",
    ]
    files = {}
    for name in plot_names:
        png_path = output_dir / f"{prefix}_{name}.png"
        if png_path.exists():
            files[name] = png_path

    logger.info(f"R Codon plots written to {output_dir}")
    return files
