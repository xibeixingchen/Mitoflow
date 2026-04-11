"""Nucleotide diversity (Pi) visualization for plant mitochondrial genomes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def plot_pi_bar(
    result,
    output_path: Path,
    dpi: int = 300,
    figsize: Optional[tuple] = None,
    hotspot_threshold: float = 0.01,
) -> Path:
    """Plot nucleotide diversity (Pi) bar chart for all regions.

    Regions are sorted by Pi value. Hotspot regions (Pi > threshold) are
    highlighted in red. CDS and IGS regions are color-coded.

    Args:
        result: PiResult from calculate_pi().
        output_path: Output file path.
        dpi: Resolution.
        figsize: Figure size; auto-sized if None.
        hotspot_threshold: Pi threshold for hotspot marking.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    if not result.regions:
        return _write_empty_plot(output_path, "No Pi data available")

    # Sort regions by Pi value
    regions = sorted(result.regions, key=lambda r: r.pi, reverse=True)

    names = [r.name for r in regions]
    pi_values = [r.pi for r in regions]
    types = [r.region_type for r in regions]

    # Colors: CDS=blue, IGS=orange, hotspot=red
    colors = []
    for r in regions:
        if r.is_hotspot:
            colors.append("#F44336")  # red
        elif r.region_type == "CDS":
            colors.append("#2196F3")  # blue
        else:
            colors.append("#FF9800")  # orange

    if figsize is None:
        n = len(names)
        figsize = (max(10, n * 0.3), 6)

    fig, ax = plt.subplots(figsize=figsize)
    bars = ax.barh(range(len(names)), pi_values, color=colors, edgecolor="black", linewidth=0.3)

    # Hotspot threshold line
    ax.axvline(x=hotspot_threshold, color="red", linestyle="--", linewidth=1.0,
               label=f"Hotspot threshold (Pi={hotspot_threshold})")

    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=7, fontstyle="italic")
    ax.set_xlabel("Nucleotide Diversity (Pi)", fontsize=11)
    ax.set_title("Nucleotide Diversity (Pi) across Regions", fontsize=12, fontweight="bold")
    ax.invert_yaxis()

    # Legend
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor="#2196F3", edgecolor="black", label="CDS"),
        Patch(facecolor="#FF9800", edgecolor="black", label="IGS"),
        Patch(facecolor="#F44336", edgecolor="black", label=f"Hotspot (Pi>{hotspot_threshold})"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=9)
    ax.grid(axis="x", alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"Pi bar chart saved to {output_path}")
    return output_path


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
