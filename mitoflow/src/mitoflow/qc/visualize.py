"""QC visualization for mitochondrial genome assembly quality.

Generates radar chart, gauge chart, and dimension score bar chart.
Uses R (ggplot2 + eoffice) when available, falls back to matplotlib.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def plot_all_qc(
    result,
    output_dir: Path,
    prefix: str = "mitoflow",
    dpi: int = 300,
) -> dict[str, Path]:
    """Generate QC plots.

    Tries R visualization first, falls back to matplotlib.

    Args:
        result: QCResult from QCEngine.run().
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
        from .visualize_r import check_r_qc_available, plot_qc_with_r
        if check_r_qc_available():
            logger.info("Using R (ggplot2 + eoffice) for QC visualization")
            return plot_qc_with_r(result, output_dir, prefix, dpi)
    except Exception as e:
        logger.warning(f"R visualization unavailable, falling back to matplotlib: {e}")

    # Fallback: matplotlib
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.warning("matplotlib not installed, skipping QC plots")
        return {}

    score = result.score
    files = {}

    # 1. Radar chart
    dimensions = ["Completeness", "Contiguity", "Correctness", "Contamination", "Structure"]
    scores = [
        score.completeness_score, score.contiguity_score,
        score.correctness_score, score.contamination_score,
        score.structure_score,
    ]

    angles = np.linspace(0, 2 * np.pi, len(dimensions), endpoint=False).tolist()
    scores_plot = scores + [scores[0]]
    angles_plot = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    ax.fill(angles_plot, scores_plot, color="#2196F3", alpha=0.25)
    ax.plot(angles_plot, scores_plot, color="#2196F3", linewidth=2)
    ax.scatter(angles, scores, c="#1565C0", s=50, zorder=5)

    for angle, dim, val in zip(angles, dimensions, scores):
        ax.text(angle, val + 8, f"{val:.0f}", ha="center", va="center", fontsize=9, fontweight="bold")

    ax.set_xticks(angles)
    ax.set_xticklabels(dimensions, fontsize=10)
    ax.set_ylim(0, 110)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_title(f"QC Radar — Overall: {score.overall_score:.0f}/100 (Grade {score.overall_grade})",
                 fontsize=13, fontweight="bold", pad=20)
    plt.tight_layout()
    path = output_dir / f"{prefix}_qc_radar.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    files["qc_radar"] = path

    # 2. Dimension scores bar chart
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = []
    for s in scores:
        if s >= 90:
            colors.append("#4CAF50")
        elif s >= 75:
            colors.append("#8BC34A")
        elif s >= 60:
            colors.append("#FF9800")
        elif s >= 40:
            colors.append("#FF5722")
        else:
            colors.append("#F44336")

    weights = [0.35, 0.15, 0.25, 0.15, 0.10]
    y_pos = range(len(dimensions))
    ax.barh(y_pos, scores, color=colors, edgecolor="black", linewidth=0.3, height=0.6)
    ax.axvline(x=60, color="red", linestyle="--", linewidth=0.8, label="Annotation-ready (60)")
    ax.axvline(x=75, color="blue", linestyle=":", linewidth=0.8, label="Good (75)")

    for i, (s, w) in enumerate(zip(scores, weights)):
        ax.text(s + 1, i, f"{s:.0f} (w={w})", va="center", fontsize=9)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(dimensions)
    ax.set_xlabel("Score (0-100)")
    ax.set_title(f"QC Dimension Scores — Overall: {score.overall_score:.0f}/100 ({score.overall_grade})",
                 fontsize=12, fontweight="bold")
    ax.set_xlim(0, 115)
    ax.legend(fontsize=8)
    plt.tight_layout()
    path = output_dir / f"{prefix}_qc_summary.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    files["qc_summary"] = path

    # 3. Gauge-like summary
    fig, ax = plt.subplots(figsize=(6, 3))
    gc = "#4CAF50" if score.overall_grade in ("A", "B") else "#FF9800" if score.overall_grade == "C" else "#F44336"
    ax.barh([0], [score.overall_score], color=gc, height=0.4, edgecolor="black", linewidth=0.3)
    ax.barh([0], [100 - score.overall_score], left=[score.overall_score], color="#E0E0E0", height=0.4, edgecolor="black", linewidth=0.3)
    ax.text(score.overall_score / 2, 0, f"{score.overall_score:.0f}/100\nGrade {score.overall_grade}",
            ha="center", va="center", fontsize=12, fontweight="bold", color="white" if score.overall_score > 30 else "black")
    status = "PASS - Annotation Ready" if score.annotation_ready else "FAIL - Needs Improvement"
    status_color = "#4CAF50" if score.annotation_ready else "#F44336"
    ax.text(50, -0.5, status, ha="center", va="center", fontsize=11, fontweight="bold", color=status_color)
    ax.set_xlim(0, 100)
    ax.set_ylim(-1, 0.5)
    ax.set_axis_off()
    ax.set_title("Assembly Quality Score", fontsize=12, fontweight="bold")
    plt.tight_layout()
    path = output_dir / f"{prefix}_qc_gauge.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    files["qc_gauge"] = path

    logger.info(f"Matplotlib QC plots written to {output_dir}")
    return files
