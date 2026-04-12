"""Repeat visualization using matplotlib (fallback when R is unavailable).

Generates plots for SSR, tandem, and long repeat detection results.
For publication-quality ggplot2 plots, use visualize_r.py instead.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ssr import SSRResult
    from .tandem import TandemRepeatResult
    from .long_repeat import LongRepeatResult

logger = logging.getLogger(__name__)

# Colors matching R
SSR_COLORS = {
    "mono": "#e74c3c", "di": "#3498db", "tri": "#2ecc71",
    "tetra": "#f39c12", "penta": "#9b59b6", "hexa": "#1abc9c",
}
LONG_TYPE_COLORS = {
    "forward": "#e74c3c", "reverse": "#3498db",
    "complement": "#2ecc71", "palindromic": "#f39c12",
}


def plot_all_repeat(
    ssr_result: "SSRResult",
    tandem_result: "TandemRepeatResult",
    long_result: "LongRepeatResult",
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
    genome_length: int = 0,
) -> dict[str, Path]:
    """Generate repeat plots (R first, matplotlib fallback).

    Args:
        ssr_result: SSRResult from detect_ssr().
        tandem_result: TandemRepeatResult from detect_tandem_repeats().
        long_result: LongRepeatResult from detect_long_repeats().
        output_dir: Output directory.
        prefix: File name prefix.
        dpi: Resolution for PNG.
        genome_length: Total genome length in bp (for long repeat map).

    Returns:
        Dict mapping plot name to output path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Try R visualization first
    try:
        from .visualize_r import check_r_repeat_available, plot_repeat_with_r
        if check_r_repeat_available():
            logger.info("Using R (ggplot2 + eoffice) for Repeat visualization")
            return plot_repeat_with_r(
                ssr_result, tandem_result, long_result,
                output_dir, prefix, dpi, genome_length=genome_length,
            )
    except Exception as e:
        logger.warning(f"R visualization unavailable, falling back to matplotlib: {e}")

    # Fallback: matplotlib
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np
    except ImportError:
        logger.warning("matplotlib not installed, skipping repeat plots")
        return {}

    files = {}

    # 1. SSR distribution by category
    if ssr_result and ssr_result.ssrs:
        cats = ssr_result.by_category()
        cat_order = ["mono", "di", "tri", "tetra", "penta", "hexa"]
        counts = [len(cats.get(c, [])) for c in cat_order]
        colors = [SSR_COLORS[c] for c in cat_order]

        fig, ax = plt.subplots(figsize=(7, 5))
        ax.bar(cat_order, counts, color=colors, edgecolor="black", linewidth=0.5)
        for i, v in enumerate(counts):
            if v > 0:
                ax.text(i, v + 0.1, str(v), ha="center", fontsize=10)
        ax.set_xlabel("SSR Category")
        ax.set_ylabel("Count")
        ax.set_title("SSR Distribution by Category")
        plt.tight_layout()
        path = output_dir / f"{prefix}_repeat_ssr_dist.png"
        fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        files["repeat_ssr_dist"] = path

        # 2. Top SSR motifs
        motif_counts: dict[str, int] = {}
        for s in ssr_result.ssrs:
            motif_counts[s.motif] = motif_counts.get(s.motif, 0) + 1
        top_motifs = sorted(motif_counts.items(), key=lambda x: -x[1])[:20]
        if top_motifs:
            fig, ax = plt.subplots(figsize=(8, max(4, len(top_motifs) * 0.35)))
            motifs = [m[0] for m in top_motifs][::-1]
            mcounts = [m[1] for m in top_motifs][::-1]
            ax.barh(motifs, mcounts, color="#3498db", edgecolor="black", linewidth=0.5)
            ax.set_xlabel("Count")
            ax.set_title("Top SSR Motifs")
            plt.tight_layout()
            path = output_dir / f"{prefix}_repeat_ssr_motif.png"
            fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
            plt.close(fig)
            files["repeat_ssr_motif"] = path

    # 3. Tandem repeat period distribution
    if tandem_result and tandem_result.repeats:
        fig, ax = plt.subplots(figsize=(7, 5))
        periods = [r.period_size for r in tandem_result.repeats]
        ax.hist(periods, bins=30, color="#2ecc71", edgecolor="black", linewidth=0.3)
        ax.set_xlabel("Period Size (bp)")
        ax.set_ylabel("Count")
        ax.set_title("Tandem Repeat Period Size Distribution")
        plt.tight_layout()
        path = output_dir / f"{prefix}_repeat_tandem_period.png"
        fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        files["repeat_tandem_period"] = path

    # 4. Long repeat genome map
    if long_result and long_result.repeat_pairs and genome_length > 0:
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot([0, genome_length], [0, 0], color="#2c3e50", linewidth=4,
                solid_capstyle="round")

        for i, rp in enumerate(long_result.repeat_pairs):
            color = "#e74c3c" if rp.orientation == "direct" else "#3498db"
            y_off = 0.5 + i * 0.6

            rect1 = mpatches.FancyBboxPatch(
                (rp.copy1_start, -0.15), rp.copy1_end - rp.copy1_start, 0.3,
                boxstyle="round,pad=10", facecolor=color, edgecolor="black",
                linewidth=0.5, alpha=0.8, zorder=2)
            ax.add_patch(rect1)
            rect2 = mpatches.FancyBboxPatch(
                (rp.copy2_start, -0.15), rp.copy2_end - rp.copy2_start, 0.3,
                boxstyle="round,pad=10", facecolor=color, edgecolor="black",
                linewidth=0.5, alpha=0.8, zorder=2)
            ax.add_patch(rect2)

            mid1 = (rp.copy1_start + rp.copy1_end) / 2
            mid2 = (rp.copy2_start + rp.copy2_end) / 2
            arc_h = y_off + 0.3
            theta = np.linspace(0, np.pi, 80)
            arc_x = mid1 + (mid2 - mid1) * (1 - np.cos(theta)) / 2
            arc_y = arc_h * np.sin(theta)
            ax.plot(arc_x, arc_y, color=color, linewidth=1.5, alpha=0.7)
            ax.text((mid1 + mid2) / 2, arc_h + 0.15,
                    f"{rp.repeat_id} ({rp.length:,} bp)",
                    ha="center", va="bottom", fontsize=7, color=color)

        ax.set_xlim(-genome_length * 0.02, genome_length * 1.02)
        ax.set_ylim(-0.7, max(1.5, 0.8 + len(long_result.repeat_pairs) * 0.6 + 0.8))
        ax.set_yticks([])
        ax.set_title(f"Long Repeat Map ({len(long_result.repeat_pairs)} pairs)")
        plt.tight_layout()
        path = output_dir / f"{prefix}_repeat_long_map.png"
        fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        files["repeat_long_map"] = path

    # 5. Long repeat type pie chart
    if long_result and long_result.repeat_pairs:
        type_counts: dict[str, int] = {}
        for rp in long_result.repeat_pairs:
            type_counts[rp.type] = type_counts.get(rp.type, 0) + 1
        if type_counts:
            fig, ax = plt.subplots(figsize=(6, 6))
            labels = list(type_counts.keys())
            sizes = list(type_counts.values())
            colors = [LONG_TYPE_COLORS.get(l, "#95a5a6") for l in labels]
            ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%",
                   startangle=90)
            ax.set_title("Long Repeat Type Distribution")
            path = output_dir / f"{prefix}_repeat_long_type.png"
            fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
            plt.close(fig)
            files["repeat_long_type"] = path

    logger.info(f"Matplotlib Repeat plots written to {output_dir}")
    return files
