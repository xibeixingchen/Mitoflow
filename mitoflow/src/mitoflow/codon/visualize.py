"""Codon usage visualization for plant mitochondrial genomes.

Generates publication-quality plots from CodonUsageResult data:
- RSCU heatmaps across genes
- ENC vs GC3s scatter plots with Wright's expected curve
- Codon usage bar charts
- Amino acid frequency plots
- PR2 parity bias plots
- Neutrality plots (GC12 vs GC3s)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def plot_rscu_heatmap(
    result,
    output_path: Path,
    top_genes: int = 30,
    dpi: int = 300,
    figsize: Optional[tuple] = None,
) -> Path:
    """Plot RSCU heatmap across genes.

    Rows = genes (top N by codon count), columns = sense codons grouped
    by amino acid. Uses seaborn clustermap-style coloring.

    Args:
        result: CodonUsageResult from analyze_codon_usage().
        output_path: Output file (PNG/PDF/SVG).
        top_genes: Maximum number of genes to show.
        dpi: Output resolution.
        figsize: Figure size; auto-sized if None.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    try:
        import seaborn as sns
        has_seaborn = True
    except ImportError:
        has_seaborn = False

    genes = sorted(result.per_gene_rscu.keys())[:top_genes]
    if not genes:
        logger.warning("No genes for RSCU heatmap")
        return _write_empty_plot(output_path, "No gene RSCU data available")

    # Collect codons from overall RSCU
    from .analysis import CODON_TABLE
    SENSE_CODONS = [c for c, aa in CODON_TABLE.items() if aa != "*"]
    codons = sorted(SENSE_CODONS)

    # Build matrix
    matrix = []
    row_labels = []
    for gene in genes:
        rscu = result.per_gene_rscu.get(gene, {})
        values = [rscu.get(c, 0.0) for c in codons]
        matrix.append(values)
        row_labels.append(gene)

    data = np.array(matrix)

    # Group codon columns by amino acid
    aa_order = []
    codon_order = []
    seen_aa = set()
    for codon in codons:
        aa = CODON_TABLE.get(codon, "?")
        if aa not in seen_aa:
            aa_order.append(aa)
            seen_aa.add(aa)

    # Sort codons by amino acid
    from collections import defaultdict
    aa_codons = defaultdict(list)
    for codon in codons:
        aa = CODON_TABLE.get(codon, "?")
        if aa != "*":
            aa_codons[aa].append(codon)

    sorted_codons = []
    for aa in aa_order:
        sorted_codons.extend(sorted(aa_codons.get(aa, [])))

    # Reorder columns
    codon_idx = {c: i for i, c in enumerate(codons)}
    col_order = [codon_idx[c] for c in sorted_codons if c in codon_idx]
    data = data[:, col_order]
    col_labels = sorted_codons

    if figsize is None:
        figsize = (max(16, len(col_labels) * 0.35), max(6, len(row_labels) * 0.35))

    fig, ax = plt.subplots(figsize=figsize)

    if has_seaborn:
        sns.heatmap(
            data, ax=ax, cmap="YlOrRd", vmin=0, vmax=3,
            xticklabels=col_labels, yticklabels=row_labels,
            linewidths=0.3, linecolor="white",
            cbar_kws={"label": "RSCU", "shrink": 0.6},
        )
    else:
        im = ax.imshow(data, cmap="YlOrRd", vmin=0, vmax=3, aspect="auto")
        ax.set_xticks(range(len(col_labels)))
        ax.set_xticklabels(col_labels, rotation=90, fontsize=6)
        ax.set_yticks(range(len(row_labels)))
        ax.set_yticklabels(row_labels, fontsize=6)
        fig.colorbar(im, ax=ax, shrink=0.6, label="RSCU")

    # Add amino acid separator lines
    prev_aa = None
    for i, codon in enumerate(col_labels):
        aa = CODON_TABLE.get(codon, "?")
        if prev_aa is not None and aa != prev_aa:
            ax.axvline(x=i, color="black", linewidth=0.8)
        prev_aa = aa

    ax.set_title("RSCU Heatmap", fontsize=12, fontweight="bold")
    ax.set_xlabel("Codon")
    ax.set_ylabel("Gene")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"RSCU heatmap saved to {output_path}")
    return output_path


def plot_enc_gc3s(
    result,
    output_path: Path,
    dpi: int = 300,
    figsize: tuple = (8, 6),
) -> Path:
    """Plot ENC vs GC3s with Wright's expected ENC curve.

    Each point is a gene. The expected curve shows the relationship
    if codon usage is determined solely by GC3s mutation bias.

    Args:
        result: CodonUsageResult.
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

    from .analysis import calculate_enc_expected

    genes = list(result.per_gene_enc.keys())
    enc_values = [result.per_gene_enc[g] for g in genes]
    gc3s_values = [result.per_gene_gc3s[g] for g in genes]

    if not genes:
        return _write_empty_plot(output_path, "No ENC/GC3s data available")

    fig, ax = plt.subplots(figsize=figsize)

    # Expected ENC curve (Wright 1990)
    gc3s_range = np.linspace(0.01, 0.99, 200)
    enc_expected = [calculate_enc_expected(g) for g in gc3s_range]
    ax.plot(gc3s_range, enc_expected, "k--", linewidth=1.5, label="Expected (Wright 1990)")

    # Gene points
    ax.scatter(gc3s_values, enc_values, c="#2196F3", alpha=0.6, s=30, edgecolors="black", linewidths=0.3)

    # Mean point
    if enc_values:
        ax.scatter(
            [result.mean_gc3s], [result.mean_enc],
            c="red", s=100, marker="*", zorder=5, label=f"Mean (ENC={result.mean_enc:.1f}, GC3s={result.mean_gc3s:.3f})",
        )

    ax.set_xlabel("GC3s", fontsize=11)
    ax.set_ylabel("ENC (Effective Number of Codons)", fontsize=11)
    ax.set_title("ENC-plot: ENC vs GC3s", fontsize=12, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(20, 61)
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"ENC-GC3s plot saved to {output_path}")
    return output_path


def plot_codon_usage_bar(
    result,
    output_path: Path,
    top_n: int = 20,
    dpi: int = 300,
    figsize: tuple = (12, 5),
) -> Path:
    """Bar chart of most-used codons with RSCU values.

    Args:
        result: CodonUsageResult.
        output_path: Output file.
        top_n: Number of top codons to show.
        dpi: Resolution.
        figsize: Figure size.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from .analysis import CODON_TABLE

    counts = result.overall_codon_count
    rscu = result.overall_rscu

    if not counts:
        return _write_empty_plot(output_path, "No codon count data available")

    # Sort by count descending
    sorted_codons = sorted(counts.keys(), key=lambda c: counts[c], reverse=True)[:top_n]
    labels = []
    count_values = []
    rscu_values = []
    colors = []

    for codon in sorted_codons:
        aa = CODON_TABLE.get(codon, "?")
        labels.append(f"{codon}\n({aa})")
        count_values.append(counts[codon])
        rscu_values.append(rscu.get(codon, 0))
        # Color: preferred (RSCU>1.5) green, avoided (RSCU<0.5) red, neutral blue
        r = rscu.get(codon, 1)
        if r > 1.5:
            colors.append("#4CAF50")
        elif r < 0.5:
            colors.append("#F44336")
        else:
            colors.append("#2196F3")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

    # Counts
    bars = ax1.bar(range(len(labels)), count_values, color=colors, edgecolor="black", linewidth=0.3)
    ax1.set_xticks(range(len(labels)))
    ax1.set_xticklabels(labels, fontsize=7)
    ax1.set_ylabel("Count")
    ax1.set_title(f"Top {top_n} Codons by Usage")
    ax1.grid(axis="y", alpha=0.3)

    # RSCU
    ax2.bar(range(len(labels)), rscu_values, color=colors, edgecolor="black", linewidth=0.3)
    ax2.axhline(y=1.0, color="black", linestyle="--", linewidth=0.8, label="RSCU=1 (no bias)")
    ax2.set_xticks(range(len(labels)))
    ax2.set_xticklabels(labels, fontsize=7)
    ax2.set_ylabel("RSCU")
    ax2.set_title("RSCU Values")
    ax2.legend(fontsize=8)
    ax2.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"Codon usage bar chart saved to {output_path}")
    return output_path


def plot_aa_frequency(
    result,
    output_path: Path,
    dpi: int = 300,
    figsize: tuple = (10, 5),
) -> Path:
    """Amino acid frequency bar chart.

    Args:
        result: CodonUsageResult.
        output_path: Output file.
        dpi: Resolution.
        figsize: Figure size.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    aa_freq = result.overall_aa_freq
    if not aa_freq:
        return _write_empty_plot(output_path, "No amino acid data available")

    total = sum(aa_freq.values())
    sorted_aa = sorted(aa_freq.keys(), key=lambda a: aa_freq[a], reverse=True)
    labels = sorted_aa
    freqs = [aa_freq[aa] / total * 100 for aa in sorted_aa]

    fig, ax = plt.subplots(figsize=figsize)
    ax.bar(range(len(labels)), freqs, color="#5C6BC0", edgecolor="black", linewidth=0.3)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_xlabel("Amino Acid")
    ax.set_ylabel("Frequency (%)")
    ax.set_title("Amino Acid Frequency", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"AA frequency plot saved to {output_path}")
    return output_path


def plot_pr2_bias(
    result,
    output_path: Path,
    dpi: int = 300,
    figsize: tuple = (7, 7),
) -> Path:
    """Plot PR2 bias (Parity Rule 2) at third codon position.

    X-axis: A3/(A3+T3), Y-axis: G3/(G3+C3).
    Center (0.5, 0.5) = no bias. Deviation indicates mutation/selection.

    Args:
        result: CodonUsageResult.
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

    genes = list(result.per_gene_pr2.keys())
    if not genes:
        return _write_empty_plot(output_path, "No PR2 data available")

    at_values = []
    gc_values = []
    for gene in genes:
        pr2 = result.per_gene_pr2[gene]
        a, t = pr2.get("A", 0), pr2.get("T", 0)
        g, c = pr2.get("G", 0), pr2.get("C", 0)
        if (a + t) > 0:
            at_values.append(a / (a + t))
        else:
            at_values.append(0.5)
        if (g + c) > 0:
            gc_values.append(g / (g + c))
        else:
            gc_values.append(0.5)

    fig, ax = plt.subplots(figsize=figsize)
    ax.scatter(at_values, gc_values, c="#2196F3", alpha=0.6, s=30, edgecolors="black", linewidths=0.3)
    ax.axhline(y=0.5, color="gray", linestyle="--", linewidth=0.8)
    ax.axvline(x=0.5, color="gray", linestyle="--", linewidth=0.8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("A3 / (A3 + T3)", fontsize=11)
    ax.set_ylabel("G3 / (G3 + C3)", fontsize=11)
    ax.set_title("PR2 Bias Plot", fontsize=12, fontweight="bold")

    # Quadrant labels
    ax.text(0.25, 0.75, "G/A bias", ha="center", va="center", fontsize=9, color="gray")
    ax.text(0.75, 0.75, "G/T bias", ha="center", va="center", fontsize=9, color="gray")
    ax.text(0.25, 0.25, "C/A bias", ha="center", va="center", fontsize=9, color="gray")
    ax.text(0.75, 0.25, "C/T bias", ha="center", va="center", fontsize=9, color="gray")

    ax.grid(True, alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"PR2 bias plot saved to {output_path}")
    return output_path


def plot_neutrality(
    result,
    output_path: Path,
    dpi: int = 300,
    figsize: tuple = (7, 7),
) -> Path:
    """Plot neutrality analysis: GC12 vs GC3s.

    Points on the diagonal = mutation-driven (neutral).
    Points below diagonal = selection-driven.

    Args:
        result: CodonUsageResult.
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

    genes = list(result.per_gene_gc12.keys())
    if not genes:
        return _write_empty_plot(output_path, "No GC12/GC3s data available")

    gc12 = [result.per_gene_gc12[g] for g in genes]
    gc3s = [result.per_gene_gc3s[g] for g in genes]

    fig, ax = plt.subplots(figsize=figsize)
    ax.scatter(gc3s, gc12, c="#2196F3", alpha=0.6, s=30, edgecolors="black", linewidths=0.3)

    # Diagonal reference line (neutral evolution)
    lims = [0, 1]
    ax.plot(lims, lims, "k--", linewidth=1.0, label="Neutral (y=x)")

    # Regression line
    if len(gc3s) > 2:
        coeffs = np.polyfit(gc3s, gc12, 1)
        x_fit = np.linspace(min(gc3s) - 0.02, max(gc3s) + 0.02, 100)
        y_fit = np.polyval(coeffs, x_fit)
        ax.plot(x_fit, y_fit, "r-", linewidth=1.5,
                label=f"Regression (slope={coeffs[0]:.3f})")

    ax.set_xlabel("GC3s", fontsize=11)
    ax.set_ylabel("GC12", fontsize=11)
    ax.set_title("Neutrality Plot: GC12 vs GC3s", fontsize=12, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"Neutrality plot saved to {output_path}")
    return output_path


def plot_enc_gc3s_enhanced(
    result,
    output_path: Path,
    distance_threshold: float = 10.0,
    dpi: int = 300,
    figsize: tuple = (8, 6),
) -> Path:
    """Plot ENC vs GC3s with significance markers for genes far from expected curve.

    Args:
        result: CodonUsageResult.
        output_path: Output file.
        distance_threshold: Genes with ENC this far below expected are flagged.
        dpi: Resolution.
        figsize: Figure size.

    Returns:
        Path to saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from .analysis import calculate_enc_expected

    genes = list(result.per_gene_enc.keys())
    if not genes:
        return _write_empty_plot(output_path, "No ENC/GC3s data available")

    enc_values = [result.per_gene_enc[g] for g in genes]
    gc3s_values = [result.per_gene_gc3s[g] for g in genes]

    # Classify genes by distance to expected curve
    normal_gc3s, normal_enc = [], []
    selected_gc3s, selected_enc = [], []

    for g, enc, gc3s in zip(genes, enc_values, gc3s_values):
        expected = calculate_enc_expected(gc3s)
        distance = expected - enc
        if distance > distance_threshold:
            selected_gc3s.append(gc3s)
            selected_enc.append(enc)
        else:
            normal_gc3s.append(gc3s)
            normal_enc.append(enc)

    fig, ax = plt.subplots(figsize=figsize)

    # Expected curve
    gc3s_range = np.linspace(0.01, 0.99, 200)
    enc_expected = [calculate_enc_expected(g) for g in gc3s_range]
    ax.plot(gc3s_range, enc_expected, "k--", linewidth=1.5, label="Expected (Wright 1990)")

    # Normal genes
    ax.scatter(normal_gc3s, normal_enc, c="#2196F3", alpha=0.6, s=30,
               edgecolors="black", linewidths=0.3, label="Mutation-driven")

    # Selected genes (far below curve)
    n_selected = len(selected_gc3s)
    if n_selected > 0:
        ax.scatter(selected_gc3s, selected_enc, c="#F44336", alpha=0.8, s=40,
                   edgecolors="black", linewidths=0.3,
                   label=f"Selection-driven ({n_selected})")

    # Mean
    ax.scatter([result.mean_gc3s], [result.mean_enc], c="red", s=100, marker="*",
               zorder=5, label=f"Mean (ENC={result.mean_enc:.1f})")

    ax.set_xlabel("GC3s", fontsize=11)
    ax.set_ylabel("ENC", fontsize=11)
    ax.set_title("ENC-plot: Selection vs Mutation Bias", fontsize=12, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(20, 61)
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"Enhanced ENC-GC3s plot saved to {output_path}")
    return output_path


def plot_all_codon(
    result,
    output_dir: Path,
    name: str = "mitoflow",
    dpi: int = 300,
) -> dict[str, Path]:
    """Generate all codon usage plots.

    Args:
        result: CodonUsageResult.
        output_dir: Output directory.
        name: File name prefix.
        dpi: Resolution.

    Returns:
        Dict mapping plot type to file path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    files["rscu_heatmap"] = plot_rscu_heatmap(result, output_dir / f"{name}_rscu_heatmap.png", dpi=dpi)
    files["enc_gc3s"] = plot_enc_gc3s(result, output_dir / f"{name}_enc_gc3s.png", dpi=dpi)
    files["enc_gc3s_enhanced"] = plot_enc_gc3s_enhanced(result, output_dir / f"{name}_enc_gc3s_selection.png", dpi=dpi)
    files["pr2_bias"] = plot_pr2_bias(result, output_dir / f"{name}_pr2_bias.png", dpi=dpi)
    files["neutrality"] = plot_neutrality(result, output_dir / f"{name}_neutrality.png", dpi=dpi)
    files["codon_bar"] = plot_codon_usage_bar(result, output_dir / f"{name}_codon_usage.png", dpi=dpi)
    files["aa_freq"] = plot_aa_frequency(result, output_dir / f"{name}_aa_frequency.png", dpi=dpi)

    logger.info(f"All codon plots written to {output_dir}")
    return files


# ── Internal helpers ─────────────────────────────────────────────

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
