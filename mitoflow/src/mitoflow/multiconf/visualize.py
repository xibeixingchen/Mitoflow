"""Multi-configuration visualization.

Generates plots for repeat-mediated multi-configuration analysis of
plant mitochondrial genomes, including repeat maps, configuration
diagrams, and recombination summary charts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

if TYPE_CHECKING:
    from .repeat_mediated import MulticonfResult, RepeatPair, SubgenomicCircle

logger = logging.getLogger(__name__)

# ── Color palette ────────────────────────────────────────────────────
REPEAT_COLORS = {"direct": "#e74c3c", "inverted": "#3498db"}
CONFIG_COLORS = ["#2ecc71", "#e67e22", "#9b59b6", "#1abc9c",
                 "#e74c3c", "#3498db", "#f1c40f", "#95a5a6"]


# ── Public API ───────────────────────────────────────────────────────

def draw_repeat_map(
    result: "MulticonfResult",
    genome_length: int,
    output_path: str | Path,
    dpi: int = 300,
) -> Path:
    """Linear genome map showing repeat pair locations with connecting arcs.

    Draws the genome as a horizontal bar and indicates each repeat pair
    with colored rectangles at both copy positions, connected by arcs
    to visualise the repeat-mediated recombination potential.

    Args:
        result: MulticonfResult from analysis.
        genome_length: Total genome length in bp.
        output_path: Destination image path.
        dpi: Resolution.

    Returns:
        Path to the saved image.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(14, 5))

    # Genome backbone
    ax.plot([0, genome_length], [0, 0], color="#2c3e50", linewidth=4,
            solid_capstyle="round", zorder=1)

    # Scale ticks
    mb = 1_000_000
    tick_step = max(1, int(genome_length / mb / 10)) * mb
    for pos in range(0, genome_length + 1, tick_step):
        ax.plot([pos, pos], [-0.15, 0.15], color="#2c3e50", linewidth=1)
        ax.text(pos, -0.35, f"{pos / mb:.1f} Mb", ha="center", fontsize=7)

    # Draw each repeat pair
    for i, rp in enumerate(result.repeat_pairs):
        color = REPEAT_COLORS.get(rp.repeat_type, "#95a5a6")
        y_off = 0.5 + i * 0.6

        # Copy 1 rectangle
        rect1 = mpatches.FancyBboxPatch(
            (rp.copy1_start, -0.15), rp.copy1_end - rp.copy1_start, 0.3,
            boxstyle="round,pad=10", facecolor=color, edgecolor="black",
            linewidth=0.5, alpha=0.8, zorder=2,
        )
        ax.add_patch(rect1)

        # Copy 2 rectangle
        rect2 = mpatches.FancyBboxPatch(
            (rp.copy2_start, -0.15), rp.copy2_end - rp.copy2_start, 0.3,
            boxstyle="round,pad=10", facecolor=color, edgecolor="black",
            linewidth=0.5, alpha=0.8, zorder=2,
        )
        ax.add_patch(rect2)

        # Connecting arc
        mid1 = (rp.copy1_start + rp.copy1_end) / 2
        mid2 = (rp.copy2_start + rp.copy2_end) / 2
        arc_height = y_off + 0.3
        theta = np.linspace(0, np.pi, 80)
        arc_x = mid1 + (mid2 - mid1) * (1 - np.cos(theta)) / 2
        arc_y = arc_height * np.sin(theta)
        ax.plot(arc_x, arc_y, color=color, linewidth=1.5, alpha=0.7)

        # Label
        label = f"{rp.id} ({rp.repeat_type}, {rp.length:,} bp)"
        ax.text((mid1 + mid2) / 2, arc_height + 0.15, label,
                ha="center", va="bottom", fontsize=7, color=color,
                fontweight="bold")

        # Recombination activity marker
        if rp.recombination_active is not None:
            status = "Active" if rp.recombination_active else "Stable"
            if rp.recombination_ratio is not None:
                status += f" ({rp.recombination_ratio:.1%})"
            ax.text((mid1 + mid2) / 2, arc_height + 0.35, status,
                    ha="center", fontsize=6, color="#7f8c8d")

    # Legend
    legend_patches = [
        mpatches.Patch(color=REPEAT_COLORS["direct"], label="Direct Repeat"),
        mpatches.Patch(color=REPEAT_COLORS["inverted"], label="Inverted Repeat"),
    ]
    ax.legend(handles=legend_patches, loc="upper left", fontsize=8)

    ax.set_title(f"Repeat Map ({len(result.repeat_pairs)} pairs, "
                 f"{genome_length:,} bp)")
    ax.set_xlim(-genome_length * 0.02, genome_length * 1.02)
    n_repeats = len(result.repeat_pairs)
    ax.set_ylim(-0.7, max(1.5, 0.8 + n_repeats * 0.6 + 0.8))
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Repeat map saved to {output_path}")
    return output_path


def draw_configuration_diagram(
    result: "MulticonfResult",
    genome_length: int,
    output_path: str | Path,
    dpi: int = 300,
) -> Path:
    """Diagram showing master circle and predicted subcircles/isomers.

    Draws circular representations for the master circle and each
    predicted subgenomic configuration, with gene counts and size
    annotations.

    Args:
        result: MulticonfResult from analysis.
        genome_length: Total genome length in bp.
        output_path: Destination image path.
        dpi: Resolution.

    Returns:
        Path to the saved image.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    configs = result.subgenomic_circles
    n_panels = 1 + len(configs)  # master + subcircles

    # Layout: row of circles
    n_cols = min(n_panels, 4)
    n_rows = (n_panels + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(n_cols * 4, n_rows * 4.5))
    if n_panels == 1:
        axes = np.array([axes])
    axes = axes.flatten()

    def _draw_circle(ax, size, label, genes, color, is_major=False):
        """Draw a single circular representation."""
        theta = np.linspace(0, 2 * np.pi, 200)
        r = 0.8
        ax.plot(r * np.cos(theta), r * np.sin(theta), color=color,
                linewidth=3 if is_major else 2)
        ax.fill(r * np.cos(theta), r * np.sin(theta),
                color=color, alpha=0.1)
        ax.text(0, 0.15, label, ha="center", va="center",
                fontsize=8, fontweight="bold")
        ax.text(0, -0.15, f"{size:,} bp", ha="center", va="center",
                fontsize=7, color="#7f8c8d")
        if genes:
            ax.text(0, -0.35, f"{len(genes)} genes", ha="center",
                    va="center", fontsize=7, color="#7f8c8d")
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-1.2, 1.2)
        ax.set_aspect("equal")
        ax.axis("off")

    # Master circle
    _draw_circle(axes[0], genome_length, "Master Circle",
                 [], "#2c3e50", is_major=True)

    # Subcircles / isomers
    for i, sg in enumerate(configs):
        color = CONFIG_COLORS[i % len(CONFIG_COLORS)]
        _draw_circle(axes[i + 1], sg.size,
                     sg.configuration.replace("_", " ").title(),
                     sg.genes, color, is_major=sg.is_major)

    # Hide unused axes
    for j in range(n_panels, len(axes)):
        axes[j].axis("off")

    title = f"Multi-configuration Diagram ({result.n_configurations} configurations)"
    if result.recombination_level != "stable":
        title += f" — Recombination: {result.recombination_level}"
    fig.suptitle(title, fontsize=12, fontweight="bold")

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Configuration diagram saved to {output_path}")
    return output_path


def plot_recombination_summary(
    result: "MulticonfResult",
    output_path: str | Path,
    dpi: int = 300,
) -> Path:
    """Summary bar chart of repeat lengths and types.

    Shows each repeat pair as a grouped bar with length in bp, coloured
    by type (direct / inverted).  Annotates recombination activity when
    available.

    Args:
        result: MulticonfResult from analysis.
        output_path: Destination image path.
        dpi: Resolution.

    Returns:
        Path to the saved image.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    repeats = result.repeat_pairs
    if not repeats:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "No large repeats detected",
                ha="center", va="center", fontsize=14, color="#95a5a6")
        ax.axis("off")
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return output_path

    labels = [rp.id for rp in repeats]
    lengths = [rp.length for rp in repeats]
    types = [rp.repeat_type for rp in repeats]
    colors = [REPEAT_COLORS.get(t, "#95a5a6") for t in types]

    fig, ax = plt.subplots(figsize=(max(8, len(repeats) * 1.2), 5))

    x = np.arange(len(repeats))
    bars = ax.bar(x, lengths, color=colors, edgecolor="black", linewidth=0.5)

    # Annotate each bar
    for i, (bar, rp) in enumerate(zip(bars, repeats)):
        # Length label
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{rp.length:,} bp\n{rp.repeat_type}",
                ha="center", va="bottom", fontsize=8)

        # Recombination ratio if available
        if rp.recombination_ratio is not None:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() / 2,
                    f"Rec: {rp.recombination_ratio:.1%}",
                    ha="center", va="center", fontsize=7,
                    color="white", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Repeat Length (bp)")
    ax.set_title("Repeat Pair Summary")

    # Legend
    legend_patches = [
        mpatches.Patch(color=REPEAT_COLORS["direct"], label="Direct"),
        mpatches.Patch(color=REPEAT_COLORS["inverted"], label="Inverted"),
    ]
    ax.legend(handles=legend_patches, loc="upper right", fontsize=9)

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Recombination summary saved to {output_path}")
    return output_path


# ── Unified API (R-first, matplotlib fallback) ──────────────────────

def plot_all_multiconf(
    result: "MulticonfResult",
    genome_length: int,
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
) -> dict[str, Path]:
    """Generate Multiconf plots (R first, matplotlib fallback).

    Args:
        result: MulticonfResult from analysis.
        genome_length: Total genome length in bp.
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
        from .visualize_r import check_r_multiconf_available, plot_multiconf_with_r
        if check_r_multiconf_available():
            logger.info("Using R (ggplot2 + eoffice) for Multiconf visualization")
            return plot_multiconf_with_r(result, output_dir, prefix, dpi, genome_length=genome_length)
    except Exception as e:
        logger.warning(f"R visualization unavailable, falling back to matplotlib: {e}")

    # Fallback: matplotlib - use existing functions
    files = {}
    path = draw_repeat_map(result, genome_length, output_dir / f"{prefix}_multiconf_repeat_map.png", dpi)
    files["multiconf_repeat_map"] = path
    path = draw_configuration_diagram(result, genome_length, output_dir / f"{prefix}_multiconf_config_diagram.png", dpi)
    files["multiconf_config_diagram"] = path
    path = plot_recombination_summary(result, output_dir / f"{prefix}_multiconf_recomb_summary.png", dpi)
    files["multiconf_recomb_summary"] = path
    logger.info(f"Matplotlib Multiconf plots written to {output_dir}")
    return files
