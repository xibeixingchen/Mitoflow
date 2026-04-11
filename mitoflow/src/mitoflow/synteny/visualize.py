"""Synteny visualization using pyGenomeViz and gbdraw.

Creates linear synteny diagrams comparing gene order across mitochondrial
genomes. Supports multi-species overviews and pairwise comparisons, with
gene arrows colored by OGDraw functional categories and synteny block
connections drawn as colored bands between tracks.

Two rendering backends are available:
- pyGenomeViz (default): Python-native linear genome visualization
- gbdraw: Publication-quality SVG-first linear diagrams with BLAST-based
  comparison links
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Reuse the gene-category helpers from the centralized config so that
# colour assignment is consistent across all MitoFlow visualisations.
from mitoflow.viz.config import ColorConfig, CATEGORY_LABELS

_color_config = ColorConfig()


def _get_gene_category(name: str, gene_type: str = "CDS") -> str:
    """Classify gene into functional category."""
    return _color_config.classify_gene(name, gene_type)


def _get_color(category: str) -> tuple:
    """Get RGB 0-1 tuple for category."""
    return _color_config.get_rgb01(category)

# ── Synteny-block link colours ────────────────────────────────────────
_SAME_ORIENTATION_COLOR = "#7fcdbb"       # teal - collinear
_INVERTED_ORIENTATION_COLOR = "#e34a33"   # red  - inverted


# ── Configuration ─────────────────────────────────────────────────────

@dataclass
class SyntenyVizConfig:
    """Configuration for synteny visualisation."""

    # Figure
    dpi: int = 300
    fig_width: float = 15.0
    track_height: float = 1.0

    # Gene feature styling
    show_labels: bool = True
    label_size: float = 8
    arrow_shaft_ratio: float = 0.5

    # Link (synteny band) styling
    same_orientation_alpha: float = 0.6
    inverted_orientation_alpha: float = 0.6

    # Custom per-category colour overrides (category_name -> RGB 0-1 tuple)
    color_scheme: dict = field(default_factory=dict)

    def get_color(self, category: str) -> tuple:
        """Return an RGB tuple (0-1 range) for *category*."""
        if category in self.color_scheme:
            return self.color_scheme[category]
        return _get_color(category)


# ── Helpers ────────────────────────────────────────────────────────────

def _rgb_to_hex(rgb_01: tuple) -> str:
    """Convert an RGB tuple (0-1) to ``#rrggbb``."""
    r, g, b = (int(c * 255) for c in rgb_01)
    return f"#{r:02x}{g:02x}{b:02x}"


def _gene_color_hex(gene_name: str, config: SyntenyVizConfig) -> str:
    """Return a hex colour string for *gene_name* based on its category."""
    category = _get_gene_category(gene_name, "CDS")
    return _rgb_to_hex(config.get_color(category))


def _estimate_genome_size(result, species: str) -> int:
    """Best-effort genome-size estimate from gene positions.

    Falls back to a nominal value when position data is unavailable.
    """
    positions = result.gene_positions.get(species, {})
    if positions:
        max_end = max(end for _gene, (start, end) in positions.items())
        return max(max_end + 500, 10_000)
    # No positions - derive from gene count as a rough proxy
    n_genes = len(result.gene_orders.get(species, []))
    return max(n_genes * 2000, 50_000)


def _collect_block_positions(result) -> dict:
    """Index synteny blocks by species pair for fast lookup.

    Returns ``{(sp_a, sp_b): [SyntenyBlock, ...]}``.
    """
    index: dict = {}
    for block in result.synteny_blocks:
        key = (block.species_a, block.species_b)
        index.setdefault(key, []).append(block)
    return index


def _few_species_msg(n: int) -> str:
    """Return an informative message for edge-case species counts."""
    if n == 0:
        return "No species data available."
    if n == 1:
        return "Only 1 species present.\nSynteny requires >= 2 species."
    return "Insufficient data for visualisation."


# ── Main visualisation ────────────────────────────────────────────────

def draw_synteny(
    result,
    output_path: Path,
    config: Optional[SyntenyVizConfig] = None,
) -> Path:
    """Draw a linear synteny diagram from a :class:`SyntenyResult`.

    One track is created per species.  Genes are drawn as coloured arrows
    (OGDraw palette) and synteny blocks are connected with coloured bands
    between adjacent tracks.  Inverted blocks are shown in a contrasting
    colour.

    Args:
        result: A :class:`SyntenyResult` produced by
            :func:`~mitoflow.synteny.collinear.detect_synteny`.
        output_path: Destination file path.  The extension determines the
            format (``.png``, ``.svg``, or ``.pdf``).
        config: Optional display settings.

    Returns:
        The *output_path* that was written.

    Raises:
        ValueError: If *result* contains fewer than 2 species.
        ImportError: If pyGenomeViz is not installed.
    """
    try:
        from pygenomeviz import GenomeViz
    except ImportError:
        raise ImportError(
            "pyGenomeViz >= 1.3.0 is required for synteny visualisation.  "
            "Install with: pip install pygenomeviz"
        )

    if config is None:
        config = SyntenyVizConfig()

    species_list = result.species_names
    n_species = len(species_list)

    # ── Edge cases ────────────────────────────────────────────────────
    if n_species < 2:
        logger.warning(
            "Need >= 2 species for synteny diagram (got %d). "
            "Writing an informative placeholder image.",
            n_species,
        )
        return _write_placeholder(output_path, config, message=_few_species_msg(n_species))

    if not result.synteny_blocks:
        logger.warning("No synteny blocks detected. Writing diagram with tracks only.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Determine segment sizes (genome sizes) ────────────────────────
    genome_sizes = {sp: _estimate_genome_size(result, sp) for sp in species_list}

    # ── Build the GenomeViz object ────────────────────────────────────
    gv = GenomeViz(
        fig_width=config.fig_width,
        fig_track_height=config.track_height,
        track_align_type="left",
        feature_track_ratio=0.25,
        link_track_ratio=1.0,
    )

    # Add one feature track per species
    tracks = {}
    for sp in species_list:
        size = genome_sizes[sp]
        track = gv.add_feature_track(
            name=sp,
            segments=size,
            labelsize=15,
        )
        tracks[sp] = track

    # ── Draw genes on each track ──────────────────────────────────────
    for sp in species_list:
        track = tracks[sp]
        gene_order = result.gene_orders.get(sp, [])
        positions = result.gene_positions.get(sp, {})

        for gene in gene_order:
            if gene in positions:
                start, end = positions[gene]
            else:
                # Synthesise positions from order index so features are still drawn
                idx = gene_order.index(gene)
                start = idx * 2000 + 1
                end = start + 1500

            strand = 1 if start <= end else -1
            s, e = (start, end) if strand == 1 else (end, start)

            color_hex = _gene_color_hex(gene, config)
            label = gene if config.show_labels else ""

            track.add_feature(
                int(s),
                int(e),
                strand,
                plotstyle="arrow",
                arrow_shaft_ratio=config.arrow_shaft_ratio,
                fc=color_hex,
                ec="black",
                lw=0.3,
                label=label,
                text_kws={"size": config.label_size, "rotation": 45},
            )

    # ── Draw synteny links between adjacent tracks ────────────────────
    block_index = _collect_block_positions(result)

    for i in range(len(species_list) - 1):
        sp_upper = species_list[i]
        sp_lower = species_list[i + 1]

        # Direct pair
        blocks = list(block_index.get((sp_upper, sp_lower), []))

        # Also check reversed pair - synteny detection may have stored
        # (sp_lower, sp_upper) for some blocks.
        for blk in block_index.get((sp_lower, sp_upper), []):
            blocks.append(blk)

        if not blocks:
            continue

        for blk in blocks:
            # Normalise so that a_start/a_end refer to sp_upper,
            # b_start/b_end refer to sp_lower.
            if blk.species_a == sp_upper:
                a_start, a_end = blk.start_a, blk.end_a
                b_start, b_end = blk.start_b, blk.end_b
            else:
                a_start, a_end = blk.start_b, blk.end_b
                b_start, b_end = blk.start_a, blk.end_a

            # Ensure start < end
            if a_start > a_end:
                a_start, a_end = a_end, a_start
            if b_start > b_end:
                b_start, b_end = b_end, b_start

            is_inverted = blk.orientation == "inverted"
            link_color = (
                _INVERTED_ORIENTATION_COLOR if is_inverted
                else _SAME_ORIENTATION_COLOR
            )
            alpha = (
                config.inverted_orientation_alpha if is_inverted
                else config.same_orientation_alpha
            )

            try:
                gv.add_link(
                    (sp_upper, int(a_start), int(a_end)),
                    (sp_lower, int(b_start), int(b_end)),
                    color=link_color,
                    inverted_color=_INVERTED_ORIENTATION_COLOR,
                    alpha=alpha,
                )
            except Exception as exc:
                logger.debug(
                    "Skipping link %s-%s (%d-%d -> %d-%d): %s",
                    sp_upper, sp_lower, a_start, a_end, b_start, b_end, exc,
                )

    # ── Save with legend ──────────────────────────────────────────────
    _savefig_with_legend(gv, output_path, config, result)
    logger.info("Synteny diagram saved to %s", output_path)
    return output_path


# ── Pairwise comparison ───────────────────────────────────────────────

def draw_pairwise_synteny(
    result,
    output_path: Path,
    species_a: Optional[str] = None,
    species_b: Optional[str] = None,
    config: Optional[SyntenyVizConfig] = None,
) -> Path:
    """Draw a simplified pairwise synteny comparison.

    Selects two species from *result* and draws their gene tracks with
    synteny links.  When the result contains more than two species,
    callers should specify *species_a* and *species_b*; otherwise the
    first two species are used.

    Args:
        result: A :class:`SyntenyResult`.
        output_path: Destination file (PNG / SVG / PDF).
        species_a: Name of the first species (``None`` -> first in result).
        species_b: Name of the second species (``None`` -> second in result).
        config: Optional display settings.

    Returns:
        Path to the written image.
    """
    try:
        from pygenomeviz import GenomeViz
    except ImportError:
        raise ImportError(
            "pyGenomeViz >= 1.3.0 is required.  "
            "Install with: pip install pygenomeviz"
        )

    if config is None:
        config = SyntenyVizConfig()

    species_list = result.species_names
    if len(species_list) < 2:
        return _write_placeholder(output_path, config, message=_few_species_msg(len(species_list)))

    if species_a is None:
        species_a = species_list[0]
    if species_b is None:
        species_b = species_list[1]

    if species_a not in species_list or species_b not in species_list:
        raise ValueError(
            f"Requested species ({species_a!r}, {species_b!r}) not in result "
            f"(available: {species_list})"
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    genome_sizes = {
        sp: _estimate_genome_size(result, sp)
        for sp in (species_a, species_b)
    }

    gv = GenomeViz(
        fig_width=config.fig_width,
        fig_track_height=config.track_height * 1.5,
        track_align_type="left",
        feature_track_ratio=0.3,
        link_track_ratio=1.2,
    )

    # Build a mini result for legend generation
    pair_result = _make_pair_result(result, species_a, species_b)

    for sp in (species_a, species_b):
        track = gv.add_feature_track(
            name=sp,
            segments=genome_sizes[sp],
            labelsize=18,
        )

        gene_order = result.gene_orders.get(sp, [])
        positions = result.gene_positions.get(sp, {})

        for gene in gene_order:
            if gene in positions:
                start, end = positions[gene]
            else:
                idx = gene_order.index(gene)
                start = idx * 2000 + 1
                end = start + 1500

            strand = 1 if start <= end else -1
            s, e = (start, end) if strand == 1 else (end, start)

            track.add_feature(
                int(s), int(e), strand,
                plotstyle="arrow",
                arrow_shaft_ratio=config.arrow_shaft_ratio,
                fc=_gene_color_hex(gene, config),
                ec="black",
                lw=0.3,
                label=gene if config.show_labels else "",
                text_kws={"size": config.label_size, "rotation": 45},
            )

    # ── Links ─────────────────────────────────────────────────────────
    for blk in result.synteny_blocks:
        pair = {blk.species_a, blk.species_b}
        if pair != {species_a, species_b}:
            continue

        if blk.species_a == species_a:
            a_s, a_e = blk.start_a, blk.end_a
            b_s, b_e = blk.start_b, blk.end_b
        else:
            a_s, a_e = blk.start_b, blk.end_b
            b_s, b_e = blk.start_a, blk.end_a

        if a_s > a_e:
            a_s, a_e = a_e, a_s
        if b_s > b_e:
            b_s, b_e = b_e, b_s

        is_inv = blk.orientation == "inverted"
        gv.add_link(
            (species_a, int(a_s), int(a_e)),
            (species_b, int(b_s), int(b_e)),
            color=_INVERTED_ORIENTATION_COLOR if is_inv else _SAME_ORIENTATION_COLOR,
            inverted_color=_INVERTED_ORIENTATION_COLOR,
            alpha=config.inverted_orientation_alpha if is_inv else config.same_orientation_alpha,
        )

    _savefig_with_legend(gv, output_path, config, pair_result)
    logger.info("Pairwise synteny diagram saved to %s", output_path)
    return output_path


# ── Gene-order conservation heatmap ───────────────────────────────────

def draw_gene_order_heatmap(
    result,
    output_path: Path,
    dpi: int = 300,
    figsize: Optional[tuple] = None,
) -> Path:
    """Draw a heatmap of gene-order conservation across species.

    For every pair of species the cell value is the fraction of shared
    genes that belong to collinear synteny blocks (i.e. the proportion of
    the shared gene set that is in conserved order).

    Args:
        result: A :class:`SyntenyResult`.
        output_path: Destination file (PNG / SVG / PDF).
        dpi: Output resolution.
        figsize: Matplotlib figure size; auto-sized when ``None``.

    Returns:
        Path to the written image.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        raise ImportError("matplotlib and numpy are required for the heatmap.")

    species_list = result.species_names
    n = len(species_list)

    if n < 2:
        return _write_placeholder(
            output_path,
            SyntenyVizConfig(dpi=dpi),
            message=_few_species_msg(n),
        )

    # Build conservation matrix
    gene_sets = {sp: set(result.gene_orders.get(sp, [])) for sp in species_list}
    block_index = _collect_block_positions(result)

    matrix = np.zeros((n, n))
    for i in range(n):
        matrix[i, i] = 1.0  # self-comparison is perfect
        for j in range(i + 1, n):
            sp_a, sp_b = species_list[i], species_list[j]
            shared = gene_sets[sp_a] & gene_sets[sp_b]
            if not shared:
                matrix[i, j] = matrix[j, i] = 0.0
                continue

            # Count genes in synteny blocks for this pair
            block_genes = set()
            for blk in block_index.get((sp_a, sp_b), []):
                block_genes.update(blk.genes_a)
            for blk in block_index.get((sp_b, sp_a), []):
                block_genes.update(blk.genes_a)

            conserved = len(shared & block_genes) / len(shared)
            matrix[i, j] = matrix[j, i] = conserved

    # Plot
    if figsize is None:
        side = max(5, n * 1.2 + 1.5)
        figsize = (side, side)

    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(matrix, cmap="YlOrRd", vmin=0, vmax=1, aspect="equal")

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(species_list, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(species_list, fontsize=9)

    # Annotate cells
    for i in range(n):
        for j in range(n):
            val = matrix[i, j]
            colour = "white" if val > 0.5 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=8, color=colour)

    ax.set_title(
        "Gene Order Conservation\n(fraction of shared genes in synteny)",
        fontsize=11,
    )
    fig.colorbar(im, ax=ax, shrink=0.8, label="Conservation fraction")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    logger.info("Gene-order heatmap saved to %s", output_path)
    return output_path


# ── Internal utilities ────────────────────────────────────────────────

def _make_pair_result(result, species_a: str, species_b: str):
    """Build a lightweight two-species SyntenyResult for legend generation."""
    from mitoflow.synteny.collinear import SyntenyResult

    pair_result = SyntenyResult()
    pair_result.species_names = [species_a, species_b]
    pair_result.gene_orders = {
        sp: result.gene_orders.get(sp, [])
        for sp in (species_a, species_b)
    }
    pair_result.gene_positions = {
        sp: result.gene_positions.get(sp, {})
        for sp in (species_a, species_b)
    }
    pair_result.synteny_blocks = [
        blk for blk in result.synteny_blocks
        if {blk.species_a, blk.species_b} == {species_a, species_b}
    ]
    return pair_result


def _write_placeholder(
    output_path: Path,
    config: SyntenyVizConfig,
    message: str,
) -> Path:
    """Write a small image with an informational message."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        # As a last resort, write a text file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        txt = output_path.with_suffix(".txt")
        txt.write_text(message + "\n")
        logger.warning("Wrote placeholder text to %s (matplotlib unavailable)", txt)
        return txt

    fig, ax = plt.subplots(figsize=(6, 2))
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12,
            transform=ax.transAxes, wrap=True)
    ax.set_axis_off()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=config.dpi, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    logger.info("Placeholder image saved to %s", output_path)
    return output_path


def _savefig_with_legend(gv, output_path: Path, config: SyntenyVizConfig, result) -> None:
    """Plot the GenomeViz figure and save with a colour-banded legend.

    Because pyGenomeViz builds the matplotlib figure lazily inside
    ``plotfig()``, we call that first, attach our legend, then save
    manually.
    """
    from matplotlib.patches import Patch
    import matplotlib.pyplot as plt

    # Collect categories present in the data
    used_categories: set = set()
    for sp in result.species_names:
        for gene in result.gene_orders.get(sp, []):
            cat = _get_gene_category(gene, "CDS")
            used_categories.add(cat)

    fig = gv.plotfig(dpi=config.dpi)

    handles = []
    for cat in sorted(used_categories):
        label = CATEGORY_LABELS.get(cat, cat)
        color = _rgb_to_hex(config.get_color(cat))
        handles.append(Patch(
            facecolor=color, edgecolor="black",
            linewidth=0.5, label=label,
        ))

    # Orientation legend entries
    handles.append(Patch(
        facecolor=_SAME_ORIENTATION_COLOR, edgecolor="black",
        linewidth=0.5, label="Collinear block",
    ))
    handles.append(Patch(
        facecolor=_INVERTED_ORIENTATION_COLOR, edgecolor="black",
        linewidth=0.5, label="Inverted block",
    ))

    if handles:
        fig.legend(
            handles=handles,
            loc="lower left",
            fontsize=7,
            ncol=3,
            framealpha=0.85,
            edgecolor="grey",
        )

    fig.savefig(
        str(output_path),
        dpi=config.dpi,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
        pad_inches=0.5,
    )
    plt.close(fig)


# ── gbdraw-based synteny visualisation ────────────────────────────────

def check_gbdraw_available() -> bool:
    """Check whether the gbdraw package is importable."""
    try:
        import gbdraw  # noqa: F401
        return True
    except ImportError:
        return False


def _run_tblastx(
    query_fasta: Path,
    subject_fasta: Path,
    output_path: Path,
    evalue: float = 1e-5,
) -> Path:
    """Run tblastx between two FASTA files and return the output path.

    Args:
        query_fasta: Query genome FASTA.
        subject_fasta: Subject genome FASTA.
        output_path: Path for tabular BLAST output.
        evalue: E-value threshold.

    Returns:
        Path to the BLAST output file.
    """
    cmd = [
        "tblastx",
        "-query", str(query_fasta),
        "-subject", str(subject_fasta),
        "-out", str(output_path),
        "-outfmt", "6",
        "-evalue", str(evalue),
    ]
    logger.info("Running tblastx: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"tblastx failed: {result.stderr}")
    return output_path


def _extract_fasta_from_gbk(gbk_path: Path, output_fasta: Path) -> Path:
    """Extract genome sequence from GenBank to FASTA."""
    from Bio import SeqIO
    record = SeqIO.read(str(gbk_path), "genbank")
    SeqIO.write(record, str(output_fasta), "fasta")
    return output_fasta


def draw_synteny_gbdraw(
    genbank_files: list[Path],
    output_path: Path,
    species_names: Optional[list[str]] = None,
    palette: str = "default",
    format: str = "png",
    evalue: float = 1e-5,
    identity: float = 70.0,
) -> Path:
    """Draw a linear synteny diagram using gbdraw.

    Loads GenBank records, runs pairwise tblastx to discover homologous
    regions, then uses gbdraw's ``assemble_linear_diagram_from_records``
    to produce a publication-quality linear comparison diagram.

    Args:
        genbank_files: List of GenBank file paths (>= 2).
        output_path: Destination file path.
        species_names: Display names for each genome.
        palette: gbdraw color palette name.
        format: Output format (png, svg, pdf).
        evalue: BLAST E-value threshold.
        identity: Minimum identity %% for BLAST hits.

    Returns:
        Path to the written image.

    Raises:
        ImportError: If gbdraw is not installed.
        ValueError: If fewer than 2 GenBank files provided.
    """
    try:
        from gbdraw.api import (
            assemble_linear_diagram_from_records,
            load_gbks,
            save_figure_to,
        )
    except ImportError:
        raise ImportError(
            "gbdraw is required for gbdraw-based synteny visualisation. "
            "Install with: pip install gbdraw"
        )

    if len(genbank_files) < 2:
        raise ValueError("Need >= 2 GenBank files for synteny comparison.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load all GenBank records
    gbk_paths_str = [str(p) for p in genbank_files]
    records = load_gbks(gbk_paths_str, mode="linear")
    if not records:
        raise ValueError("No records found in the provided GenBank files.")

    # Set species names on records
    if species_names:
        for rec, name in zip(records, species_names):
            rec.name = name

    # Run pairwise tblastx for adjacent genomes
    with tempfile.TemporaryDirectory(prefix="mitoflow_synteny_") as tmpdir:
        # Extract FASTA files for BLAST
        fasta_files = []
        for i, gbk_path in enumerate(genbank_files):
            fasta_path = Path(tmpdir) / f"genome_{i}.fasta"
            _extract_fasta_from_gbk(gbk_path, fasta_path)
            fasta_files.append(fasta_path)

        # Run pairwise tblastx (adjacent pairs)
        blast_files = []
        for i in range(len(fasta_files) - 1):
            blast_out = Path(tmpdir) / f"pair_{i}_{i+1}.tblastx.out"
            try:
                _run_tblastx(fasta_files[i], fasta_files[i + 1], blast_out, evalue=evalue)
                blast_files.append(str(blast_out))
            except RuntimeError as e:
                logger.warning("tblastx failed for pair %d-%d: %s", i, i + 1, e)

        # Build the linear diagram with gbdraw
        canvas = assemble_linear_diagram_from_records(
            records,
            blast_files=blast_files if blast_files else None,
            default_colors_palette=palette,
            output_prefix=output_path.stem,
            legend="right",
            dinucleotide="GC",
            identity=identity,
            evalue=evalue,
        )

        # Save figure
        output_dir = str(output_path.parent)
        output_prefix = output_path.stem
        fmt_list = [format]

        try:
            save_figure_to(
                canvas,
                fmt_list,
                output_dir=output_dir,
                output_prefix=output_prefix,
                overwrite=True,
            )
        except ImportError:
            # cairosvg not available — fall back to SVG
            logger.warning("CairoSVG not installed; generating SVG instead of %s.", format.upper())
            save_figure_to(
                canvas,
                ["svg"],
                output_dir=output_dir,
                output_prefix=output_prefix,
                overwrite=True,
            )

    # Determine the actual output file
    # gbdraw saves with format extension
    actual = output_path.parent / f"{output_prefix}.{format}"
    if not actual.exists():
        actual = output_path.parent / f"{output_prefix}.svg"

    logger.info("gbdraw synteny diagram saved to %s", actual)
    return actual
