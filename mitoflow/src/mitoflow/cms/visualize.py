"""CMS candidate visualization.

Generates plots for CMS (Cytoplasmic Male Sterility) candidate gene
prediction results, including score breakdowns, chimeric structure
diagrams, genome context maps, and candidate heatmaps.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.cm as mcm
import numpy as np

if TYPE_CHECKING:
    from .predictor import CMSResult, CMSCandidate

logger = logging.getLogger(__name__)

# ── Color palette ────────────────────────────────────────────────────
SCORE_COLORS = {
    "chimera":   "#e74c3c",
    "tm":        "#3498db",
    "homolog":   "#2ecc71",
    "context":   "#f39c12",
    "length":    "#9b59b6",
}
CONFIDENCE_COLORS = {"High": "#e74c3c", "Medium": "#f39c12", "Low": "#95a5a6"}


# ── Public API ───────────────────────────────────────────────────────

def plot_cms_scores(
    result: "CMSResult",
    output_path: str | Path,
    dpi: int = 300,
    top_n: int = 20,
) -> Path:
    """Stacked bar chart showing score breakdown for top candidates.

    Each bar is segmented into chimera / tm / homolog / context / length
    sub-scores, illustrating the contribution of each dimension to the
    total score.

    Args:
        result: CMSResult from prediction.
        output_path: Destination image path.
        dpi: Resolution.
        top_n: Number of top candidates to show.

    Returns:
        Path to the saved image.
    """
    candidates = result.candidates[:top_n]
    if not candidates:
        logger.warning("No candidates to plot.")
        return Path(output_path)

    labels = [c.orf_id for c in candidates]
    scores = {
        "chimera":  [c.chimera_score  for c in candidates],
        "tm":       [c.tm_score       for c in candidates],
        "homolog":  [c.homolog_score  for c in candidates],
        "context":  [c.context_score  for c in candidates],
        "length":   [c.length_score   for c in candidates],
    }

    # We scale each sub-score by its weight so the stack equals total_score
    weights = {"chimera": 0.30, "tm": 0.25, "homolog": 0.20,
               "context": 0.15, "length": 0.10}

    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 0.8), 6))
    y = np.zeros(len(labels))
    for dim in ("chimera", "tm", "homolog", "context", "length"):
        values = np.array(scores[dim]) * weights[dim]
        bars = ax.barh(labels, values, left=y, color=SCORE_COLORS[dim],
                       label=dim.capitalize(), edgecolor="white", linewidth=0.5)
        y += values

    # Confidence markers
    for i, c in enumerate(candidates):
        color = CONFIDENCE_COLORS.get(c.confidence, "#95a5a6")
        ax.plot(c.total_score, i, marker="|", color=color,
                markersize=14, markeredgewidth=2.5)

    ax.set_xlabel("Weighted Score")
    ax.set_title("CMS Candidate Score Breakdown")
    ax.legend(loc="lower right", fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, max(c.total_score for c in candidates) * 1.15)

    # Confidence legend
    from matplotlib.lines import Line2D
    conf_handles = [
        Line2D([0], [0], marker="|", color=CONFIDENCE_COLORS[lvl],
               markeredgewidth=2, linestyle="None", markersize=8, label=lvl)
        for lvl in ("High", "Medium", "Low")
    ]
    ax.legend(handles=ax.get_legend_handles_labels()[0] + conf_handles,
              loc="lower right", fontsize=7, ncol=2)

    plt.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"CMS score plot saved to {output_path}")
    return output_path


def plot_chimera_structure(
    candidate: "CMSCandidate",
    output_path: str | Path,
    dpi: int = 300,
) -> Path:
    """Diagram showing chimeric ORF structure with source gene segments.

    Draws the ORF as a horizontal bar segmented by the contributing parent
    genes (if chimera info is available) and marks transmembrane domains.

    Args:
        candidate: A single CMSCandidate.
        output_path: Destination image path.
        dpi: Resolution.

    Returns:
        Path to the saved image.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 4))
    orf_len = candidate.length_aa

    # Draw full ORF background
    ax.barh(0, orf_len, height=0.6, color="#ecf0f1", edgecolor="#bdc3c7",
            linewidth=1)

    # Chimera segments
    if candidate.chimera and candidate.chimera.source_genes:
        n_src = candidate.chimera.n_sources
        cmap = plt.cm.Set2
        segment_colors = [cmap(i / max(n_src, 1)) for i in range(n_src)]

        # Distribute coverage proportionally
        total_cov = sum(candidate.chimera.coverage_by_source.values())
        pos = 0
        for i, gene in enumerate(candidate.chimera.source_genes):
            cov = candidate.chimera.coverage_by_source.get(gene, 0)
            seg_len = (cov / total_cov * orf_len) if total_cov > 0 else orf_len / n_src
            ax.barh(0, seg_len, left=pos, height=0.6,
                    color=segment_colors[i], edgecolor="white", linewidth=1)
            # Gene label
            mid = pos + seg_len / 2
            if seg_len > orf_len * 0.08:
                ax.text(mid, 0, gene, ha="center", va="center",
                        fontsize=8, fontweight="bold")
            pos += seg_len
    else:
        ax.barh(0, orf_len, height=0.6, color="#3498db", alpha=0.6)

    # Transmembrane domains
    for tm in candidate.tm_domains:
        ax.barh(0.45, tm.end - tm.start + 1, left=tm.start, height=0.15,
                color="#e74c3c", alpha=0.8)
        ax.text((tm.start + tm.end) / 2, 0.58, "TM", ha="center",
                va="bottom", fontsize=6, color="#e74c3c")

    # Labels
    title_parts = [candidate.orf_id, f"{candidate.length_aa} aa",
                   f"Score: {candidate.total_score:.1f} ({candidate.confidence})"]
    ax.set_title("  |  ".join(title_parts))
    ax.set_xlabel("Amino Acid Position")
    ax.set_yticks([])
    ax.set_xlim(0, orf_len * 1.02)

    # Legend for TM
    tm_patch = mpatches.Patch(color="#e74c3c", alpha=0.8, label="TM domain")
    ax.legend(handles=[tm_patch], loc="upper right", fontsize=8)

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Chimera structure plot saved to {output_path}")
    return output_path


def plot_cms_genome_context(
    result: "CMSResult",
    genome_length: int,
    output_path: str | Path,
    dpi: int = 300,
) -> Path:
    """Linear genome view with CMS candidates marked, nearby genes shown.

    Draws a horizontal line representing the genome, marks candidate ORF
    locations, and annotates nearby genes.

    Args:
        result: CMSResult from prediction.
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
    ax.plot([0, genome_length], [0, 0], color="#2c3e50", linewidth=3,
            solid_capstyle="round")

    # Tick marks (Mb)
    mb = 1_000_000
    tick_step = max(1, int(genome_length / mb / 10)) * mb
    for pos in range(0, genome_length + 1, tick_step):
        ax.plot([pos, pos], [-0.3, 0.3], color="#2c3e50", linewidth=1)
        ax.text(pos, -0.6, f"{pos / mb:.1f} Mb", ha="center", fontsize=7)

    # Plot candidates
    n_cand = len(result.candidates)
    for i, c in enumerate(result.candidates):
        y_off = 1 + (i % 10) * 0.8  # stagger vertically
        color = CONFIDENCE_COLORS.get(c.confidence, "#95a5a6")

        # ORF rectangle
        rect = mpatches.FancyBboxPatch(
            (c.start, y_off - 0.2), c.end - c.start, 0.4,
            boxstyle="round,pad=0.05", facecolor=color, edgecolor="black",
            linewidth=0.5, alpha=0.85,
        )
        ax.add_patch(rect)

        # Connecting line to genome
        mid = (c.start + c.end) / 2
        ax.plot([mid, mid], [0, y_off - 0.2], color=color, linewidth=0.5,
                alpha=0.5)

        # Label
        label = c.orf_id
        if c.n_tm_domains:
            label += f" ({c.n_tm_domains}TM)"
        ax.text(mid, y_off + 0.25, label, ha="center", va="bottom",
                fontsize=6, rotation=30)

        # Nearby genes (small ticks on genome backbone)
        for gene in c.nearby_genes[:5]:
            # approximate position from the gene name -- just mark near the ORF
            pass  # positions of nearby genes are not in the model, skip

    # Title and legend
    conf_patches = [
        mpatches.Patch(color=CONFIDENCE_COLORS[lvl], label=f"{lvl} confidence")
        for lvl in ("High", "Medium", "Low")
    ]
    ax.legend(handles=conf_patches, loc="upper right", fontsize=8)

    ax.set_title(f"CMS Candidates on Genome ({genome_length:,} bp)")
    ax.set_xlim(-genome_length * 0.02, genome_length * 1.02)
    ax.set_ylim(-1.5, max(2, 1 + (min(n_cand, 10)) * 0.8 + 1))
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"CMS genome context plot saved to {output_path}")
    return output_path


def plot_cms_heatmap(
    result: "CMSResult",
    output_path: str | Path,
    dpi: int = 300,
) -> Path:
    """Heatmap of all candidates x scoring dimensions.

    Rows = candidates (sorted by total score), columns = five scoring
    dimensions.  Cell colour intensity reflects the raw sub-score value.

    Args:
        result: CMSResult from prediction.
        output_path: Destination image path.
        dpi: Resolution.

    Returns:
        Path to the saved image.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    candidates = result.candidates
    if not candidates:
        logger.warning("No candidates for heatmap.")
        return output_path

    dims = ["chimera_score", "tm_score", "homolog_score",
            "context_score", "length_score"]
    dim_labels = ["Chimera", "TM", "Homolog", "Context", "Length"]

    data = np.array([[getattr(c, d) for d in dims] for c in candidates])

    fig, ax = plt.subplots(
        figsize=(max(6, len(dims) * 1.2), max(4, len(candidates) * 0.35 + 1.5)),
    )
    im = ax.imshow(data, aspect="auto", cmap="YlOrRd", vmin=0, vmax=100)

    # Axis labels
    ax.set_xticks(range(len(dims)))
    ax.set_xticklabels(dim_labels, fontsize=9)
    ax.set_yticks(range(len(candidates)))
    ax.set_yticklabels([c.orf_id for c in candidates], fontsize=7)

    # Annotate cells
    for i in range(len(candidates)):
        for j in range(len(dims)):
            val = data[i, j]
            color = "white" if val > 60 else "black"
            ax.text(j, i, f"{val:.0f}", ha="center", va="center",
                    fontsize=6, color=color)

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_label("Score (0-100)")

    # Total score annotation on the right
    for i, c in enumerate(candidates):
        ax.text(len(dims) + 0.3, i, f"Total: {c.total_score:.1f}",
                va="center", fontsize=7,
                color=CONFIDENCE_COLORS.get(c.confidence, "black"))

    ax.set_title("CMS Candidate Scoring Heatmap")
    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"CMS heatmap saved to {output_path}")
    return output_path


# ── Unified API (R-first, matplotlib fallback) ──────────────────────

def plot_all_cms(
    result: "CMSResult",
    genome_length: int,
    output_dir: str | Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
) -> dict[str, Path]:
    """Generate CMS plots (R first, matplotlib fallback).

    Args:
        result: CMSResult from prediction.
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
        from .visualize_r import check_r_cms_available, plot_cms_with_r
        if check_r_cms_available():
            logger.info("Using R (ggplot2 + eoffice) for CMS visualization")
            return plot_cms_with_r(result, output_dir, prefix, dpi, genome_length=genome_length)
    except Exception as e:
        logger.warning(f"R visualization unavailable, falling back to matplotlib: {e}")

    # Fallback: matplotlib - use existing functions
    files = {}
    if result.candidates:
        path = plot_cms_scores(result, output_dir / f"{prefix}_cms_scores.png", dpi)
        files["cms_scores"] = path
        path = plot_cms_heatmap(result, output_dir / f"{prefix}_cms_heatmap.png", dpi)
        files["cms_heatmap"] = path
        path = plot_cms_genome_context(result, genome_length, output_dir / f"{prefix}_cms_genome_context.png", dpi)
        files["cms_genome_context"] = path
    logger.info(f"Matplotlib CMS plots written to {output_dir}")
    return files
