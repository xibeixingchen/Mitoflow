"""Linear genome visualization using pyGenomeViz.

Produces OGDraw-style linear genome maps with:
- Gene arrows on forward/reverse tracks
- Color coding by functional category
- GC content profile below
- Scale bar and gene labels
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Import color scheme from config
from .config import ColorConfig, CATEGORY_LABELS

# Single source of truth for colors and classification
_color_config = ColorConfig()


def _get_gene_category(gene_name: str, gene_type: str = "CDS") -> str:
    """Classify gene into functional category using centralized config."""
    return _color_config.classify_gene(gene_name, gene_type)


def _get_color(category: str) -> tuple:
    """Get RGB color tuple (0-1 range) for a category."""
    return _color_config.get_rgb01(category)


@dataclass
class LinearVizConfig:
    """Configuration for linear genome visualization."""
    show_labels: bool = True
    label_size: float = 7
    show_gc: bool = True
    gc_window: int = 500
    dpi: int = 300
    fig_width: float = 18.0
    track_height_ratio: float = 0.7
    custom_colors: dict = field(default_factory=dict)

    def get_color(self, category: str) -> tuple:
        if category in self.custom_colors:
            return self.custom_colors[category]
        return _get_color(category)


def _rgb_to_hex(rgb_01: tuple) -> str:
    r, g, b = (int(c * 255) for c in rgb_01)
    return f"#{r:02x}{g:02x}{b:02x}"


def draw_linear_genome(
    genbank_path: Path,
    output_path: Path,
    organism: str = "",
    config: Optional[LinearVizConfig] = None,
    show_gc: bool = True,
    show_labels: bool = True,
    dpi: int = 300,
) -> Path:
    """Draw OGDraw-style linear genome map from GenBank file.

    Args:
        genbank_path: Input GenBank (.gb/.gbk) file.
        output_path: Output image path (PNG/SVG/PDF).
        organism: Organism name.
        config: Visualization config.
        show_gc: Show GC content track.
        show_labels: Show gene labels.
        dpi: Output resolution.

    Returns:
        Path to output image.
    """
    if config is None:
        config = LinearVizConfig()

    try:
        from pygenomeviz import GenomeViz
        from pygenomeviz.parser import Genbank
    except ImportError:
        raise ImportError("pyGenomeViz required: pip install pygenomeviz")

    gbk = Genbank(str(genbank_path))
    seqid2size = gbk.get_seqid2size()
    seqid2features = gbk.get_seqid2features()
    seqid2seq = gbk.get_seqid2seq()

    gv = GenomeViz(fig_width=config.fig_width, feature_track_ratio=config.track_height_ratio)

    used_categories = set()

    for seqid, size in seqid2size.items():
        track = gv.add_feature_track(seqid, size)
        features = seqid2features.get(seqid, [])

        # Draw features on the track
        for feat in features:
            if feat.type not in ("gene", "CDS", "tRNA", "rRNA"):
                continue
            if feat.type == "exon":
                continue

            gene_name = ""
            if "gene" in feat.qualifiers:
                gene_name = feat.qualifiers["gene"][0]
            elif "locus_tag" in feat.qualifiers:
                gene_name = feat.qualifiers["locus_tag"][0]
            elif "product" in feat.qualifiers:
                gene_name = feat.qualifiers["product"][0][:15]
            if not gene_name:
                continue

            category = _get_gene_category(gene_name, feat.type)
            color = config.get_color(category)
            used_categories.add(category)

            strand = feat.location.strand or 1

            try:
                if strand == 1:
                    track.add_feature(
                        int(feat.location.start), int(feat.location.end),
                        strand,
                        plotstyle="arrow",
                        fc=_rgb_to_hex(color),
                        ec="black", lw=0.5, alpha=0.9,
                        label=gene_name if show_labels and config.show_labels else None,
                        labelsize=config.label_size,
                    )
                else:
                    track.add_feature(
                        int(feat.location.start), int(feat.location.end),
                        strand,
                        plotstyle="arrow",
                        fc=_rgb_to_hex(color),
                        ec="black", lw=0.5, alpha=0.9,
                        label=gene_name if show_labels and config.show_labels else None,
                        labelsize=config.label_size,
                    )
            except Exception:
                try:
                    track.add_feature(
                        int(feat.location.start), int(feat.location.end),
                        strand,
                        fc=_rgb_to_hex(color), ec="black", lw=0.5, alpha=0.9,
                    )
                except Exception:
                    continue

        # Scale ticks
        try:
            tick_interval = max(5000, int(size / 20))
            track.set_scale_xticks(tick_interval)
        except Exception:
            pass

        # GC content
        if show_gc and config.show_gc:
            seq = seqid2seq.get(seqid, "")
            if seq:
                try:
                    import numpy as np
                    window = config.gc_window
                    positions = []
                    gc_values = []
                    for i in range(0, len(seq) - window, window // 2):
                        chunk = str(seq[i:i + window]).upper()
                        gc = (chunk.count("G") + chunk.count("C")) / len(chunk) * 100
                        positions.append(i + window // 2)
                        gc_values.append(gc)

                    if positions:
                        mean_gc = np.mean(gc_values)
                        track.add_gc_plot(positions, gc_values, fc="black", alpha=0.5)
                except Exception:
                    pass

    # Add title
    title_parts = []
    if organism:
        title_parts.append(organism)
    total_size = sum(seqid2size.values())
    title_parts.append(f"{total_size:,} bp")
    gv.set_title("  |  ".join(title_parts))

    # Save with legend
    from matplotlib.patches import Patch
    import matplotlib.pyplot as plt

    fig = gv.plotfig(dpi=config.dpi or dpi)

    legend_handles = []
    for cat in sorted(used_categories):
        label = CATEGORY_LABELS.get(cat, cat)
        legend_handles.append(Patch(
            facecolor=_rgb_to_hex(config.get_color(cat)),
            edgecolor="black", linewidth=0.5, label=label,
        ))

    if legend_handles:
        fig.legend(
            handles=legend_handles, loc="lower left",
            fontsize=6, ncol=3, framealpha=0.85, edgecolor="grey",
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=config.dpi or dpi, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)

    logger.info(f"Linear genome map saved to {output_path}")
    return output_path


def draw_linear_comparison(
    genbank_files: list,
    output_path: Path,
    species_names: Optional[list] = None,
    dpi: int = 300,
    fig_width: float = 20.0,
) -> Path:
    """Multi-track linear comparison of gene order across species.

    Each species gets its own track, allowing visual comparison of
    gene arrangements.

    Args:
        genbank_files: List of GenBank file paths (>=2).
        output_path: Output image path.
        species_names: Optional display names.
        dpi: Resolution.
        fig_width: Figure width.

    Returns:
        Path to output image.
    """
    try:
        from pygenomeviz import GenomeViz
        from pygenomeviz.parser import Genbank
    except ImportError:
        raise ImportError("pyGenomeViz required: pip install pygenomeviz")

    n = len(genbank_files)
    names = species_names or [Path(f).stem for f in genbank_files]

    gv = GenomeViz(fig_width=fig_width, feature_track_ratio=0.8)

    used_categories = set()

    for i, gbk_path in enumerate(genbank_files):
        sp_name = names[i] if i < len(names) else f"species_{i}"
        gbk = Genbank(str(gbk_path))
        seqid2size = gbk.get_seqid2size()
        seqid2features = gbk.get_seqid2features()

        for seqid, size in seqid2size.items():
            track_name = f"{sp_name}"
            track = gv.add_feature_track(track_name, size)
            features = seqid2features.get(seqid, [])

            for feat in features:
                if feat.type not in ("gene", "CDS", "tRNA", "rRNA"):
                    continue
                gene_name = ""
                if "gene" in feat.qualifiers:
                    gene_name = feat.qualifiers["gene"][0]
                elif "locus_tag" in feat.qualifiers:
                    gene_name = feat.qualifiers["locus_tag"][0]
                if not gene_name:
                    continue

                category = _get_gene_category(gene_name, feat.type)
                color = _get_color(category)
                used_categories.add(category)

                strand = feat.location.strand or 1
                try:
                    track.add_feature(
                        int(feat.location.start), int(feat.location.end),
                        strand,
                        plotstyle="arrow",
                        fc=_rgb_to_hex(color),
                        ec="black", lw=0.4, alpha=0.85,
                        labelsize=6,
                    )
                except Exception:
                    continue

    gv.set_title("Linear Genome Comparison")

    from matplotlib.patches import Patch
    import matplotlib.pyplot as plt

    fig = gv.plotfig(dpi=dpi)

    legend_handles = []
    for cat in sorted(used_categories):
        label = CATEGORY_LABELS.get(cat, cat)
        legend_handles.append(Patch(
            facecolor=_rgb_to_hex(_get_color(cat)),
            edgecolor="black", linewidth=0.5, label=label,
        ))
    if legend_handles:
        fig.legend(
            handles=legend_handles, loc="lower left",
            fontsize=6, ncol=3, framealpha=0.85, edgecolor="grey",
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    logger.info(f"Linear comparison saved to {output_path}")
    return output_path
