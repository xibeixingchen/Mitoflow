"""MTPT visualization (R first, matplotlib fallback).

Tries R (ggplot2 + eoffice) for PNG/PDF/PPTX, falls back to matplotlib.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .detector import MTPTResult

logger = logging.getLogger(__name__)

# Category colors matching R
CAT_COLORS = {
    "intact": "#4CAF50",
    "degenerate": "#FF9800",
    "fragment": "#2196F3",
    "ancient": "#9E9E9E",
}


def plot_all_mtpt(
    result: MTPTResult,
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
) -> dict[str, Path]:
    """Generate MTPT plots (R first, matplotlib fallback).

    Args:
        result: MTPTResult from detect_mtpt().
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
        from .visualize_r import check_r_mtpt_available, plot_mtpt_with_r
        if check_r_mtpt_available():
            logger.info("Using R (ggplot2 + eoffice) for MTPT visualization")
            return plot_mtpt_with_r(result, output_dir, prefix, dpi)
    except Exception as e:
        logger.warning(f"R visualization unavailable, falling back to matplotlib: {e}")

    # Fallback: matplotlib
    if not result.regions:
        logger.info("No MTPT regions to plot")
        return {}

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        logger.warning("matplotlib not installed, skipping MTPT plots")
        return {}

    files = {}
    regions = result.regions

    # 1. Category barplot
    cat_names = ["intact", "degenerate", "fragment", "ancient"]
    cats = {}
    for r in regions:
        cats[r.category] = cats.get(r.category, 0) + 1
    counts = [cats.get(c, 0) for c in cat_names]
    colors = [CAT_COLORS.get(c, "#999") for c in cat_names]

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(cat_names, counts, color=colors, edgecolor="black", linewidth=0.5)
    for i, v in enumerate(counts):
        if v:
            ax.text(i, v + 0.1, str(v), ha="center", fontsize=10)
    ax.set_xlabel("Category")
    ax.set_ylabel("MTPT Count")
    ax.set_title("MTPT Distribution by Category")
    plt.tight_layout()
    path = output_dir / f"{prefix}_mtpt_barplot.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    files["mtpt_barplot"] = path

    # 2. Identity histogram
    fig, ax = plt.subplots(figsize=(7, 5))
    for cat in cat_names:
        cat_ids = [r.identity for r in regions if r.category == cat]
        if cat_ids:
            ax.hist(cat_ids, bins=20, alpha=0.7, color=CAT_COLORS.get(cat, "#999"),
                    label=cat, edgecolor="black", linewidth=0.3)
    ax.set_xlabel("Identity (%)")
    ax.set_ylabel("Count")
    ax.set_title("MTPT Identity Distribution")
    ax.legend()
    plt.tight_layout()
    path = output_dir / f"{prefix}_mtpt_identity.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    files["mtpt_identity"] = path

    # 3. Mito coverage dot plot
    fig, ax = plt.subplots(figsize=(9, 5))
    for r in regions:
        mid = (r.mito_start + r.mito_end) / 2
        ax.scatter(mid, r.identity, c=CAT_COLORS.get(r.category, "#999"),
                   s=max(5, r.length / 50), alpha=0.7, edgecolors="black", linewidths=0.3)
    handles = [mpatches.Patch(color=CAT_COLORS[c], label=c) for c in cat_names if c in cats]
    ax.legend(handles=handles)
    ax.set_xlabel("Mitochondrial Position (bp)")
    ax.set_ylabel("Identity (%)")
    ax.set_title("MTPT Coverage on Mitochondrial Genome")
    plt.tight_layout()
    path = output_dir / f"{prefix}_mtpt_mito_map.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    files["mtpt_mito_map"] = path

    # 4. CP gene coverage bar
    gene_counts: dict[str, int] = {}
    for r in regions:
        for g in r.cp_genes_covered:
            gene_counts[g] = gene_counts.get(g, 0) + 1

    if gene_counts:
        sorted_genes = sorted(gene_counts.items(), key=lambda x: -x[1])
        g_names = [g for g, _ in sorted_genes]
        g_counts = [c for _, c in sorted_genes]

        fig, ax = plt.subplots(figsize=(8, max(4, len(g_names) * 0.3)))
        ax.barh(range(len(g_names)), g_counts, color="#2E7D32", edgecolor="black", linewidth=0.3)
        ax.set_yticks(range(len(g_names)))
        ax.set_yticklabels(g_names, fontsize=8, fontstyle="italic")
        ax.set_xlabel("Number of MTPT Regions")
        ax.set_title("Chloroplast Genes in MTPT Regions")
        ax.invert_yaxis()
        plt.tight_layout()
        path = output_dir / f"{prefix}_mtpt_gene_coverage.png"
        fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        files["mtpt_gene_coverage"] = path

    logger.info(f"Matplotlib MTPT plots written to {output_dir}")
    return files
