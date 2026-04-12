"""NUMT visualization using matplotlib (fallback when R is unavailable).

Generates basic plots: category barplot, identity histogram, mito coverage,
chromosome distribution. For publication-quality RIdeogram ideograms,
use visualize_r.py instead.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .detector import NUMTResult

logger = logging.getLogger(__name__)

# Category colors matching R
CAT_COLORS = {"intact": "#4CAF50", "partial": "#FF9800", "chimeric": "#F44336"}


def plot_all_numt(
    result: NUMTResult,
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
) -> dict[str, Path]:
    """Generate NUMT plots (matplotlib fallback).

    Tries R visualization first, falls back to matplotlib.

    Args:
        result: NUMTResult from detect_numts().
        output_dir: Output directory.
        prefix: File name prefix.
        dpi: Resolution for PNG.

    Returns:
        Dict mapping plot name to output path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Try R visualization first
    try:
        from .visualize_r import check_r_numt_available, plot_numt_with_r
        if check_r_numt_available():
            logger.info("Using R (RIdeogram + eoffice) for NUMT visualization")
            return plot_numt_with_r(result, output_dir, prefix, dpi)
    except Exception as e:
        logger.warning(f"R visualization unavailable, falling back to matplotlib: {e}")

    # Fallback: matplotlib
    if not result.regions:
        logger.info("No NUMT regions to plot")
        return {}

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        logger.warning("matplotlib not installed, skipping NUMT plots")
        return {}

    files = {}
    regions = result.regions

    # 1. Category barplot
    cats = result.by_category()
    cat_names = ["intact", "partial", "chimeric"]
    counts = [len(cats.get(c, [])) for c in cat_names]
    colors = [CAT_COLORS[c] for c in cat_names]

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(cat_names, counts, color=colors, edgecolor="black", linewidth=0.5)
    for i, v in enumerate(counts):
        ax.text(i, v + 0.1, str(v), ha="center", fontsize=10)
    ax.set_xlabel("Category")
    ax.set_ylabel("NUMT Count")
    ax.set_title("NUMT Distribution by Category")
    plt.tight_layout()
    path = output_dir / f"{prefix}_numt_barplot.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    files["numt_barplot"] = path

    # 2. Identity histogram
    fig, ax = plt.subplots(figsize=(7, 5))
    identities = [r.identity for r in regions]
    cat_list = [r.fragment_category for r in regions]
    for cat in cat_names:
        cat_ids = [identities[i] for i in range(len(identities)) if cat_list[i] == cat]
        if cat_ids:
            ax.hist(cat_ids, bins=20, alpha=0.7, color=CAT_COLORS[cat],
                    label=cat, edgecolor="black", linewidth=0.3)
    ax.set_xlabel("Identity (%)")
    ax.set_ylabel("Count")
    ax.set_title("NUMT Identity Distribution")
    ax.legend()
    plt.tight_layout()
    path = output_dir / f"{prefix}_numt_identity.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    files["numt_identity"] = path

    # 3. Mito coverage dot plot
    fig, ax = plt.subplots(figsize=(9, 5))
    for r in regions:
        mid = (r.mito_start + r.mito_end) / 2
        ax.scatter(mid, r.identity, c=CAT_COLORS.get(r.fragment_category, "#999999"),
                   s=max(5, r.length / 50), alpha=0.7, edgecolors="black", linewidths=0.3)
    handles = [mpatches.Patch(color=CAT_COLORS[c], label=c) for c in cat_names if c in cats]
    ax.legend(handles=handles)
    ax.set_xlabel("Mitochondrial Position (bp)")
    ax.set_ylabel("Identity (%)")
    ax.set_title("NUMT Coverage on Mitochondrial Genome")
    plt.tight_layout()
    path = output_dir / f"{prefix}_numt_mito_map.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    files["numt_mito_map"] = path

    # 4. Per-chromosome distribution
    chr_counts: dict[str, int] = {}
    for r in regions:
        chr_counts[r.chr_id] = chr_counts.get(r.chr_id, 0) + 1
    sorted_chr = sorted(chr_counts.items(), key=lambda x: -x[1])

    fig, ax = plt.subplots(figsize=(max(8, len(sorted_chr) * 0.5), 5))
    chr_names = [c[0] for c in sorted_chr]
    chr_vals = [c[1] for c in sorted_chr]
    ax.bar(chr_names, chr_vals, color="#2196F3", edgecolor="black", linewidth=0.5)
    ax.set_xlabel("Nuclear Chromosome")
    ax.set_ylabel("NUMT Count")
    ax.set_title("NUMT Distribution by Nuclear Chromosome")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    path = output_dir / f"{prefix}_numt_chr_dist.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    files["numt_chr_dist"] = path

    logger.info(f"Matplotlib NUMT plots written to {output_dir}")
    return files
