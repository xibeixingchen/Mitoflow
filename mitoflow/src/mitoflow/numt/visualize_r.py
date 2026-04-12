"""NUMT visualization using R (RIdeogram + ggplot2 + eoffice).

Generates publication-quality plots in PNG, PDF, and PPTX formats.
Ideogram uses RIdeogram for nuclear chromosome karyotype with NUMT markers.

Falls back to matplotlib (visualize.py) if R or required packages are unavailable.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .detector import NUMTResult

logger = logging.getLogger(__name__)


def check_r_numt_available() -> bool:
    """Check if R with RIdeogram, ggplot2, and eoffice is available."""
    rscript = _find_rscript()
    if not rscript:
        return False

    try:
        result = subprocess.run(
            [rscript, "-e", "require(RIdeogram) && require(ggplot2) && require(eoffice)"],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _find_rscript() -> Optional[str]:
    """Find Rscript binary."""
    import shutil
    return shutil.which("Rscript")


def _build_karyotype_tsv(
    result: NUMTResult,
    nuclear_fasta: Path,
) -> str:
    """Build RIdeogram karyotype TSV content from nuclear genome FASTA.

    Format: Chr, Start, End (3-column, no centromere).
    """
    from Bio import SeqIO

    lines = ["Chr\tStart\tEnd"]
    for rec in SeqIO.parse(str(nuclear_fasta), "fasta"):
        lines.append(f"{rec.id}\t1\t{len(rec.seq)}")
    return "\n".join(lines)


def plot_numt_with_r(
    result: NUMTResult,
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
    width: float = 10.0,
    height: float = 7.0,
    nuclear_fasta: Optional[Path] = None,
) -> dict[str, Path]:
    """Generate NUMT plots using R (RIdeogram + ggplot2 + eoffice).

    Outputs PNG, PDF, and PPTX for each of 5 plot types:
    numt_ideogram, numt_barplot, numt_identity, numt_mito_map, numt_chr_dist

    Args:
        result: NUMTResult from detect_numts().
        output_dir: Output directory.
        prefix: File name prefix.
        dpi: Resolution for PNG.
        width: Figure width in inches.
        height: Figure height in inches.
        nuclear_fasta: Nuclear genome FASTA for karyotype (required for ideogram).

    Returns:
        Dict mapping plot name to primary output path (PNG).
    """
    rscript = _find_rscript()
    if not rscript:
        raise RuntimeError("Rscript not found in PATH")

    r_script = Path(__file__).parent / "numt_plots.R"
    if not r_script.exists():
        raise RuntimeError(f"R wrapper not found: {r_script}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write NUMT results to a temporary TSV for R to read
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", prefix="mitoflow_numt_", delete=False
    ) as tmp:
        tmp.write("Chr\tStart\tEnd\tMitoStart\tMitoEnd\tLength\tIdentity\tCategory\tMitoGenes\n")
        for r in result.regions:
            genes = ",".join(r.mito_genes_covered) or "none"
            tmp.write(
                f"{r.chr_id}\t{r.start}\t{r.end}\t{r.mito_start}\t{r.mito_end}\t"
                f"{r.length}\t{r.identity:.1f}\t{r.fragment_category}\t{genes}\n"
            )
        tsv_path = tmp.name

    # Write karyotype TSV for RIdeogram
    karyo_path = None
    if nuclear_fasta and nuclear_fasta.exists():
        karyo_tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", prefix="mitoflow_karyo_", delete=False
        )
        karyo_tmp.write(_build_karyotype_tsv(result, nuclear_fasta))
        karyo_tmp.close()
        karyo_path = karyo_tmp.name
    else:
        # Create a minimal karyotype from NUMT data
        karyo_tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", prefix="mitoflow_karyo_", delete=False
        )
        karyo_tmp.write("Chr\tStart\tEnd\n")
        seen_chr = set()
        for r in result.regions:
            if r.chr_id not in seen_chr:
                karyo_tmp.write(f"{r.chr_id}\t1\t{r.end + 10000}\n")
                seen_chr.add(r.chr_id)
        karyo_tmp.close()
        karyo_path = karyo_tmp.name

    out_prefix = str(output_dir / prefix)

    cmd = [
        rscript, str(r_script),
        tsv_path, out_prefix, karyo_path,
        str(width), str(height), str(dpi),
    ]

    logger.info(f"Running R NUMT visualization: {' '.join(cmd)}")

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
        if karyo_path:
            Path(karyo_path).unlink(missing_ok=True)

    # Collect output files
    plot_names = ["numt_ideogram", "numt_barplot", "numt_identity", "numt_mito_map", "numt_chr_dist"]
    files = {}
    for name in plot_names:
        png_path = output_dir / f"{prefix}_{name}.png"
        if png_path.exists():
            files[name] = png_path

    logger.info(f"R NUMT plots written to {output_dir}")
    return files
