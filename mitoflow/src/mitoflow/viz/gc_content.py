"""GC content calculation and visualization for mitochondrial genomes.

Provides sliding-window GC content profiles, GC skew analysis, and
multi-genome comparisons.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def calculate_gc_profile(
    seq: str,
    window: int = 500,
    step: int = 250,
) -> tuple[list[int], list[float], float]:
    """Calculate GC content profile along a sequence.

    Args:
        seq: DNA sequence string.
        window: Window size in bases.
        step: Step size in bases.

    Returns:
        (positions, gc_values, mean_gc)
    """
    seq = seq.upper()
    positions = []
    gc_values = []

    for i in range(0, len(seq) - window + 1, step):
        chunk = seq[i:i + window]
        gc = (chunk.count("G") + chunk.count("C")) / len(chunk) * 100
        positions.append(i + window // 2)
        gc_values.append(gc)

    mean_gc = sum(gc_values) / len(gc_values) if gc_values else 0.0
    return positions, gc_values, mean_gc


def calculate_gc_skew(
    seq: str,
    window: int = 500,
    step: int = 250,
) -> tuple[list[int], list[float]]:
    """Calculate GC skew (G-C)/(G+C) along a sequence.

    Args:
        seq: DNA sequence string.
        window: Window size.
        step: Step size.

    Returns:
        (positions, skew_values)
    """
    seq = seq.upper()
    positions = []
    skew_values = []

    for i in range(0, len(seq) - window + 1, step):
        chunk = seq[i:i + window]
        g = chunk.count("G")
        c = chunk.count("C")
        total = g + c
        skew = (g - c) / total if total > 0 else 0.0
        positions.append(i + window // 2)
        skew_values.append(skew)

    return positions, skew_values


def plot_gc_profile(
    fasta_path: Path,
    output_path: Path,
    window: int = 500,
    step: int = 250,
    show_skew: bool = True,
    dpi: int = 300,
    figsize: tuple = (12, 6),
) -> Path:
    """Plot GC content profile along genome.

    Shows GC% and optionally GC skew in a subplot below.

    Args:
        fasta_path: Input FASTA file.
        output_path: Output file (PNG/PDF/SVG).
        window: Window size in bases.
        step: Step size in bases.
        show_skew: Whether to show GC skew subplot.
        dpi: Resolution.
        figsize: Figure size.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from Bio import SeqIO

    record = next(SeqIO.parse(str(fasta_path), "fasta"))
    seq = str(record.seq).upper()

    positions, gc_values, mean_gc = calculate_gc_profile(seq, window, step)

    if not positions:
        return _write_empty_plot(output_path, "Sequence too short for GC analysis")

    n_plots = 2 if show_skew else 1
    fig, axes = plt.subplots(n_plots, 1, figsize=figsize, sharex=True)
    if n_plots == 1:
        axes = [axes]

    # GC content plot
    ax = axes[0]
    ax.plot(positions, gc_values, color="#2196F3", linewidth=0.8, alpha=0.8)
    ax.axhline(y=mean_gc, color="red", linestyle="--", linewidth=1.0,
               label=f"Mean GC = {mean_gc:.1f}%")
    ax.fill_between(positions, gc_values, mean_gc, alpha=0.2, color="#2196F3")
    ax.set_ylabel("GC Content (%)", fontsize=10)
    ax.set_title(f"GC Content Profile — {record.id} ({len(seq):,} bp)", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(min(gc_values) - 2, max(gc_values) + 2)

    # GC skew plot
    if show_skew:
        skew_positions, skew_values = calculate_gc_skew(seq, window, step)
        ax2 = axes[1]
        ax2.plot(skew_positions, skew_values, color="#FF9800", linewidth=0.8, alpha=0.8)
        ax2.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax2.fill_between(skew_positions, skew_values, 0,
                         where=[s >= 0 for s in skew_values], alpha=0.3, color="green", label="G > C")
        ax2.fill_between(skew_positions, skew_values, 0,
                         where=[s < 0 for s in skew_values], alpha=0.3, color="red", label="G < C")
        ax2.set_xlabel("Position (bp)", fontsize=10)
        ax2.set_ylabel("GC Skew", fontsize=10)
        ax2.legend(fontsize=8, loc="upper right")
        ax2.grid(True, alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"GC profile saved to {output_path}")
    return output_path


def plot_gc_comparison(
    fasta_paths: list,
    output_path: Path,
    names: Optional[list] = None,
    window: int = 500,
    dpi: int = 300,
    figsize: Optional[tuple] = None,
) -> Path:
    """Compare GC profiles across multiple genomes.

    Each genome is shown as a separate subplot with aligned GC content.

    Args:
        fasta_paths: List of FASTA file paths.
        output_path: Output file.
        names: Display names for each genome.
        window: Window size.
        dpi: Resolution.
        figsize: Figure size.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from Bio import SeqIO

    n = len(fasta_paths)
    if n == 0:
        return _write_empty_plot(output_path, "No genomes provided")

    sp_names = names or [Path(f).stem for f in fasta_paths]

    profiles = []
    for i, fa_path in enumerate(fasta_paths):
        record = next(SeqIO.parse(str(fa_path), "fasta"))
        seq = str(record.seq).upper()
        positions, gc_values, mean_gc = calculate_gc_profile(seq, window)
        profiles.append((sp_names[i], len(seq), positions, gc_values, mean_gc))

    if figsize is None:
        figsize = (14, max(4, n * 2.5))

    fig, axes = plt.subplots(n, 1, figsize=figsize, sharex=False)
    if n == 1:
        axes = [axes]

    for i, (name, seq_len, positions, gc_values, mean_gc) in enumerate(profiles):
        ax = axes[i]
        # Normalize positions to percentage
        pct_positions = [p / seq_len * 100 for p in positions]
        ax.plot(pct_positions, gc_values, linewidth=0.8, alpha=0.8)
        ax.axhline(y=mean_gc, color="red", linestyle="--", linewidth=0.8,
                   label=f"GC={mean_gc:.1f}%")
        ax.set_ylabel("GC%", fontsize=9)
        ax.set_title(f"{name} ({seq_len:,} bp)", fontsize=9, fontweight="bold", loc="left")
        ax.legend(fontsize=7, loc="upper right")
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 100)

    axes[-1].set_xlabel("Genome Position (%)", fontsize=10)
    fig.suptitle("GC Content Comparison", fontsize=12, fontweight="bold", y=1.01)
    fig.tight_layout()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"GC comparison saved to {output_path}")
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
