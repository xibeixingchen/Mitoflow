"""Ka/Ks selection pressure visualization for plant mitochondrial genes.

Generates publication-quality plots from Ka/Ks analysis results:
- Grouped bar plots of Ka/Ks ratios by gene and functional category
- Box plots showing selection pressure distribution
- Ka vs Ks scatter plots with diagonal reference lines
- Selection category pie charts
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Functional categories for grouped visualization (from calculator.py)
GENE_CATEGORIES = {
    "Complex I": ["nad1", "nad2", "nad3", "nad4", "nad4L", "nad5", "nad6", "nad7", "nad9"],
    "Complex III": ["cob"],
    "Complex IV": ["cox1", "cox2", "cox3"],
    "Complex V": ["atp1", "atp4", "atp6", "atp8", "atp9"],
    "CCM": ["ccmB", "ccmC", "ccmFC", "ccmFN"],
    "Ribosomal": [
        "rpl2", "rpl5", "rpl10", "rpl16",
        "rps1", "rps2", "rps3", "rps4", "rps7",
        "rps10", "rps12", "rps13", "rps14", "rps19",
    ],
    "Other": ["matR", "mttB", "sdh3", "sdh4"],
}

# Colors for each category
CATEGORY_COLORS = {
    "Complex I": "#FFEC00",
    "Complex III": "#C8FA28",
    "Complex IV": "#FFB4FF",
    "Complex V": "#97BE0D",
    "CCM": "#328925",
    "Ribosomal": "#DBAA73",
    "Other": "#AB259D",
}


def _gene_category(name: str) -> str:
    """Return the functional category for a gene name."""
    low = name.lower()
    for cat, genes in GENE_CATEGORIES.items():
        if low in (g.lower() for g in genes):
            return cat
    return "Other"


def _flatten_results(results) -> list:
    """Flatten list[KaKsBatchResult] -> list[KaKsResult]."""
    all_results = []
    for batch in results:
        all_results.extend(batch.results)
    return all_results


def plot_kaks_barplot(
    results,
    output_path: Path,
    dpi: int = 300,
    figsize: Optional[tuple] = None,
) -> Path:
    """Grouped bar plot of Ka/Ks ratios by gene, colored by functional category.

    Horizontal dashed line at Ka/Ks = 1 (neutral selection).
    NA/inf values shown as truncated bars.

    Args:
        results: List of KaKsBatchResult.
        output_path: Output file (PNG/PDF/SVG).
        dpi: Resolution.
        figsize: Figure size.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    flat = _flatten_results(results)
    if not flat:
        return _write_empty_plot(output_path, "No Ka/Ks results to plot")

    # Filter valid results
    valid = [r for r in flat if r.selection != "NA"]
    if not valid:
        return _write_empty_plot(output_path, "All Ka/Ks values are NA (Ks\u22480)")

    # Sort by Ka/Ks ratio
    valid.sort(key=lambda r: r.kaks_ratio)

    genes = [r.gene for r in valid]
    ratios = [r.kaks_ratio for r in valid]
    colors = [CATEGORY_COLORS.get(r.category, "#999999") for r in valid]

    n = len(genes)
    if figsize is None:
        figsize = (max(10, n * 0.4), 6)

    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(n)
    bars = ax.bar(x, ratios, color=colors, edgecolor="black", linewidth=0.3, width=0.7)

    # Neutral line
    ax.axhline(y=1.0, color="red", linestyle="--", linewidth=1.0, label="Ka/Ks = 1 (neutral)")

    ax.set_xticks(x)
    ax.set_xticklabels(genes, rotation=90, fontsize=7, ha="center")
    ax.set_ylabel("Ka/Ks", fontsize=11)
    ax.set_title("Ka/Ks Ratio by Gene", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    # Add legend for categories
    from matplotlib.patches import Patch
    used_cats = {r.category for r in valid}
    legend_handles = [
        Patch(facecolor=CATEGORY_COLORS.get(c, "#999"), edgecolor="black", label=c)
        for c in sorted(used_cats) if c in CATEGORY_COLORS
    ]
    ax.legend(
        handles=[plt.Line2D([0], [0], color="red", linestyle="--", label="Ka/Ks = 1")] + legend_handles,
        loc="upper left", fontsize=7, ncol=2,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"Ka/Ks bar plot saved to {output_path}")
    return output_path


def plot_kaks_boxplot(
    results,
    output_path: Path,
    dpi: int = 300,
    figsize: Optional[tuple] = None,
) -> Path:
    """Box plot of Ka/Ks ratios grouped by functional category.

    Args:
        results: List of KaKsBatchResult.
        output_path: Output file.
        dpi: Resolution.
        figsize: Figure size.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    flat = _flatten_results(results)
    valid = [r for r in flat if r.selection != "NA"]

    if not valid:
        return _write_empty_plot(output_path, "No valid Ka/Ks results")

    # Group by category
    from collections import defaultdict
    cat_data = defaultdict(list)
    for r in valid:
        cat_data[r.category].append(r.kaks_ratio)

    categories = sorted(cat_data.keys())
    data = [cat_data[c] for c in categories]
    colors_list = [CATEGORY_COLORS.get(c, "#999") for c in categories]

    if figsize is None:
        figsize = (max(8, len(categories) * 1.5), 6)

    fig, ax = plt.subplots(figsize=figsize)
    bp = ax.boxplot(
        data, patch_artist=True, widths=0.6,
        medianprops=dict(color="black", linewidth=1.5),
    )

    for patch, color in zip(bp["boxes"], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.8)

    ax.axhline(y=1.0, color="red", linestyle="--", linewidth=1.0, label="Ka/Ks = 1")
    ax.set_xticklabels(categories, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Ka/Ks", fontsize=11)
    ax.set_title("Ka/Ks Distribution by Functional Category", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"Ka/Ks box plot saved to {output_path}")
    return output_path


def plot_ka_vs_ks_scatter(
    results,
    output_path: Path,
    dpi: int = 300,
    figsize: tuple = (8, 7),
) -> Path:
    """Scatter plot of Ka vs Ks with diagonal reference lines.

    Diagonal lines show Ka/Ks ratios of 0.5, 1.0, and 2.0.

    Args:
        results: List of KaKsBatchResult.
        output_path: Output file.
        dpi: Resolution.
        figsize: Figure size.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    flat = _flatten_results(results)
    valid = [r for r in flat if r.selection != "NA" and r.ks > 0]

    if not valid:
        return _write_empty_plot(output_path, "No valid Ka/Ks data for scatter plot")

    ka_vals = [r.ka for r in valid]
    ks_vals = [r.ks for r in valid]
    colors = [CATEGORY_COLORS.get(r.category, "#999") for r in valid]

    fig, ax = plt.subplots(figsize=figsize)

    ax.scatter(ks_vals, ka_vals, c=colors, s=40, alpha=0.7, edgecolors="black", linewidths=0.3)

    # Reference lines
    max_val = max(max(ks_vals), max(ka_vals)) * 1.1
    x_line = np.linspace(0, max_val, 100)
    for ratio, label, style in [(0.5, "Ka/Ks=0.5", ":"), (1.0, "Ka/Ks=1.0", "--"), (2.0, "Ka/Ks=2.0", "-.")]:
        ax.plot(x_line, x_line * ratio, "k" + style, linewidth=0.8, alpha=0.6, label=label)

    ax.set_xlabel("Ks (synonymous substitutions)", fontsize=11)
    ax.set_ylabel("Ka (non-synonymous substitutions)", fontsize=11)
    ax.set_title("Ka vs Ks", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"Ka vs Ks scatter saved to {output_path}")
    return output_path


def plot_selection_pie(
    results,
    output_path: Path,
    dpi: int = 300,
    figsize: tuple = (6, 6),
) -> Path:
    """Pie chart of selection categories (purifying/neutral/positive/NA).

    Args:
        results: List of KaKsBatchResult.
        output_path: Output file.
        dpi: Resolution.
        figsize: Figure size.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    flat = _flatten_results(results)
    if not flat:
        return _write_empty_plot(output_path, "No Ka/Ks results")

    from collections import Counter
    counts = Counter(r.selection for r in flat)

    labels = []
    sizes = []
    colors = []
    explode = []

    color_map = {
        "purifying": "#4CAF50",
        "neutral": "#2196F3",
        "positive": "#F44336",
        "NA": "#9E9E9E",
    }

    for sel_type in ["purifying", "neutral", "positive", "NA"]:
        if sel_type in counts:
            labels.append(f"{sel_type.capitalize()}\n({counts[sel_type]})")
            sizes.append(counts[sel_type])
            colors.append(color_map[sel_type])
            explode.append(0.05 if sel_type == "positive" else 0)

    if not sizes:
        return _write_empty_plot(output_path, "No selection data")

    fig, ax = plt.subplots(figsize=figsize)
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, explode=explode,
        autopct="%1.1f%%", startangle=90, pctdistance=0.75,
        textprops={"fontsize": 10},
    )
    for autotext in autotexts:
        autotext.set_fontsize(9)
        autotext.set_fontweight("bold")

    ax.set_title("Selection Pressure Distribution", fontsize=12, fontweight="bold")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"Selection pie chart saved to {output_path}")
    return output_path


def plot_kaks_dotplot(
    results,
    output_path: Path,
    dpi: int = 300,
    figsize: Optional[tuple] = None,
) -> Path:
    """Horizontal dot plot of Ka/Ks ratios by gene.

    Each gene shown as a colored dot, with a red vertical line at Ka/Ks=1.
    Dots are colored by functional category.

    Args:
        results: List of KaKsBatchResult.
        output_path: Output file.
        dpi: Resolution.
        figsize: Figure size.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    flat = _flatten_results(results)
    if not flat:
        return _write_empty_plot(output_path, "No Ka/Ks results to plot")

    valid = [r for r in flat if r.selection != "NA"]
    if not valid:
        return _write_empty_plot(output_path, "All Ka/Ks values are NA (Ks\u22480)")

    # Sort by Ka/Ks ratio
    valid.sort(key=lambda r: r.kaks_ratio)

    genes = [r.gene for r in valid]
    ratios = [r.kaks_ratio for r in valid]
    colors = [CATEGORY_COLORS.get(r.category, "#999999") for r in valid]

    n = len(genes)
    if figsize is None:
        figsize = (8, max(4, n * 0.25))

    fig, ax = plt.subplots(figsize=figsize)
    y_pos = np.arange(n)

    ax.scatter(ratios, y_pos, c=colors, s=50, alpha=0.8, edgecolors="black", linewidths=0.3, zorder=3)

    # Neutral line
    ax.axvline(x=1.0, color="red", linestyle="--", linewidth=1.2, label="Ka/Ks = 1 (neutral)", zorder=2)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(genes, fontsize=7)
    ax.set_xlabel("Ka/Ks", fontsize=11)
    ax.set_title("Ka/Ks Ratio by Gene", fontsize=12, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)

    # Legend for categories
    from matplotlib.patches import Patch
    used_cats = {r.category for r in valid}
    legend_handles = [
        Patch(facecolor=CATEGORY_COLORS.get(c, "#999"), edgecolor="black", label=c)
        for c in sorted(used_cats) if c in CATEGORY_COLORS
    ]
    ax.legend(
        handles=[plt.Line2D([0], [0], color="red", linestyle="--", label="Ka/Ks = 1")] + legend_handles,
        loc="lower right", fontsize=7, ncol=2,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"Ka/Ks dot plot saved to {output_path}")
    return output_path


def plot_all_kaks(
    results,
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
) -> dict[str, Path]:
    """Generate all Ka/Ks plots.

    Args:
        results: List of KaKsBatchResult.
        output_dir: Output directory.
        prefix: File name prefix.
        dpi: Resolution.

    Returns:
        Dict mapping plot type to file path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    files["barplot"] = plot_kaks_barplot(results, output_dir / f"{prefix}_kaks_barplot.png", dpi=dpi)
    files["boxplot"] = plot_kaks_boxplot(results, output_dir / f"{prefix}_kaks_boxplot.png", dpi=dpi)
    files["dotplot"] = plot_kaks_dotplot(results, output_dir / f"{prefix}_kaks_dotplot.png", dpi=dpi)
    files["scatter"] = plot_ka_vs_ks_scatter(results, output_dir / f"{prefix}_ka_vs_ks.png", dpi=dpi)
    files["pie"] = plot_selection_pie(results, output_dir / f"{prefix}_selection_pie.png", dpi=dpi)

    logger.info(f"All Ka/Ks plots written to {output_dir}")
    return files


def _write_empty_plot(output_path: Path, message: str) -> Path:
    """Write an empty plot with a message."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 3))
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12, transform=ax.transAxes)
    ax.set_axis_off()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path
