"""RNA editing visualization (R first, matplotlib fallback).

Tries R (ggplot2 + eoffice) for PNG/PDF/PPTX, falls back to matplotlib.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from .predictor import EditingSite

logger = logging.getLogger(__name__)


def plot_all_rna_edit(
    editing_sites: list[EditingSite],
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
) -> dict[str, Path]:
    """Generate RNA editing plots (R first, matplotlib fallback).

    Args:
        editing_sites: List of EditingSite predictions.
        output_dir: Output directory.
        prefix: File name prefix.
        dpi: Resolution.

    Returns:
        Dict mapping plot name to file path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Try R visualization first
    try:
        from .visualize_r import check_r_rnaedit_available, plot_rnaedit_with_r
        if check_r_rnaedit_available():
            logger.info("Using R (ggplot2 + eoffice) for RNA editing visualization")
            return plot_rnaedit_with_r(editing_sites, output_dir, prefix, dpi)
    except Exception as e:
        logger.warning(f"R visualization unavailable, falling back to matplotlib: {e}")

    # Fallback: matplotlib
    if not editing_sites:
        logger.info("No editing sites to plot")
        return {}

    files = {}
    output_path = output_dir / f"{prefix}_editing_summary.png"
    _plot_editing_summary_mpl(editing_sites, output_path, dpi)
    files["editing_summary"] = output_path

    logger.info(f"Matplotlib RNA editing plots written to {output_dir}")
    return files


def _plot_editing_summary_mpl(
    editing_sites: list[EditingSite],
    output_path: Path,
    dpi: int = 300,
) -> Path:
    """Create matplotlib visualization of editing summary (3-panel)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sites_by_gene: dict[str, int] = defaultdict(int)
    n_syn = 0
    n_nonsyn = 0
    codon_counts = {1: 0, 2: 0, 3: 0}

    for site in editing_sites:
        sites_by_gene[site.gene] += 1
        if site.is_synonymous:
            n_syn += 1
        else:
            n_nonsyn += 1
        codon_counts[site.codon_position] = codon_counts.get(site.codon_position, 0) + 1

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(f"RNA Editing Summary ({len(editing_sites)} sites)", fontsize=14, fontweight="bold")

    # Panel 1: Bar chart of editing per gene
    ax1 = axes[0]
    sorted_genes = sorted(sites_by_gene.items(), key=lambda x: -x[1])
    gene_names = [g for g, _ in sorted_genes]
    gene_counts = [c for _, c in sorted_genes]
    bar_colors = []
    for g in gene_names:
        gene_sites = [s for s in editing_sites if s.gene == g]
        if any(getattr(s, 'is_start_codon_creation', False) for s in gene_sites):
            bar_colors.append("#e74c3c")
        elif any(getattr(s, 'is_stop_codon_removal', False) for s in gene_sites):
            bar_colors.append("#3498db")
        else:
            bar_colors.append("#2ecc71")
    ax1.barh(range(len(gene_names)), gene_counts, color=bar_colors)
    ax1.set_yticks(range(len(gene_names)))
    ax1.set_yticklabels(gene_names, fontsize=8)
    ax1.set_xlabel("Number of editing sites")
    ax1.set_title("Editing sites per gene")
    ax1.invert_yaxis()

    # Panel 2: Pie chart synonymous vs nonsynonymous
    ax2 = axes[1]
    ax2.pie([n_syn, n_nonsyn], labels=["Synonymous", "Nonsynonymous"],
            colors=["#4CAF50", "#F44336"], autopct="%1.1f%%", startangle=90)
    ax2.set_title("Editing type")

    # Panel 3: Codon position
    ax3 = axes[2]
    positions = ["Pos 1", "Pos 2", "Pos 3"]
    pos_vals = [codon_counts.get(1, 0), codon_counts.get(2, 0), codon_counts.get(3, 0)]
    ax3.bar(positions, pos_vals, color=["#FFEC00", "#C8FA28", "#97BE0D"], edgecolor="black")
    ax3.set_ylabel("Count")
    ax3.set_title("Codon position")

    plt.tight_layout()
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"RNA editing summary saved to {output_path}")
    return output_path
