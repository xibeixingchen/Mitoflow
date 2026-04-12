"""Genome visualization using gbdraw — publication-quality circular and linear diagrams.

gbdraw (https://github.com/satoshikawato/gbdraw) generates SVG-first genome diagrams
for microbes and organelles with GC content tracks, separate strand display, and
50+ built-in color palettes.

This module provides a thin wrapper around gbdraw's Python API for MitoFlow integration.
gbdraw is an optional dependency — if not installed, the viz command falls back to the
built-in v2 (pycirclize) backend.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def check_gbdraw_available() -> bool:
    """Check whether the gbdraw package is importable."""
    try:
        import gbdraw  # noqa: F401
        return True
    except ImportError:
        return False


def draw_with_gbdraw(
    genbank_path: str,
    output_path: str,
    organism: str = "",
    format: str = "png",
    gc_window: int | None = None,
    separate_strands: bool = True,
    palette: str = "default",
    labels: str = "both",
    show_gc: bool = True,
) -> dict:
    """Draw a circular genome diagram using gbdraw.

    Args:
        genbank_path: Path to the GenBank (.gb) file.
        output_path: Output file path. The extension is ignored; gbdraw determines
                     format from the *format* argument.
        organism: Organism name displayed on the diagram.
        format: Output format: "svg", "png", or "pdf". PNG/PDF require cairosvg.
        gc_window: Sliding window size for GC content track (bp). None = auto.
        separate_strands: Draw forward/reverse strands separately.
        palette: Color palette name (gbdraw ships 50+ palettes).
        labels: Label placement: "outside", "inside", or "both".
        show_gc: Whether to include the GC content track.

    Returns:
        dict with genome_length and gene_count for CLI output.
    """
    from gbdraw.api import (
        build_circular_diagram,
        load_gbks,
        save_figure_to,
        DiagramOptions,
        ColorOptions,
        OutputOptions,
    )

    # Load GenBank record
    records = load_gbks([genbank_path], mode="circular")
    if not records:
        raise ValueError(f"No records found in {genbank_path}")
    record = records[0]

    # Build options
    config_overrides = {}
    if separate_strands:
        config_overrides["strandedness"] = True

    color_opts = ColorOptions(default_colors_palette=palette)
    output_opts = OutputOptions(output_prefix=Path(output_path).stem, legend="right")

    options = DiagramOptions(
        colors=color_opts,
        output=output_opts,
        config_overrides=config_overrides if config_overrides else None,
        window=gc_window,
        species=organism if organism else None,
        dinucleotide="GC",
    )

    # Build diagram
    canvas = build_circular_diagram(record, options=options)

    # Determine output directory and format
    output_dir = str(Path(output_path).parent)
    os.makedirs(output_dir, exist_ok=True)

    # Save figure — gbdraw always produces SVG, then optionally converts
    output_prefix = Path(output_path).stem
    fmt_list = [format]

    try:
        saved = save_figure_to(
            canvas,
            fmt_list,
            output_dir=output_dir,
            output_prefix=output_prefix,
            overwrite=True,
        )
        for path in saved:
            logger.info("Generated: %s", path)
    except ImportError as exc:
        # cairosvg not available — fall back to SVG
        logger.warning(
            "CairoSVG not installed; generating SVG instead of %s. "
            "Install with: pip install gbdraw[export]",
            format.upper(),
        )
        save_figure_to(
            canvas,
            ["svg"],
            output_dir=output_dir,
            output_prefix=output_prefix,
            overwrite=True,
        )

    # Compute stats for CLI output
    seq = str(record.seq).upper()
    gene_count = sum(
        1 for f in record.features if f.type in ("gene", "CDS", "tRNA", "rRNA")
    )
    return {
        "genome_length": len(seq),
        "gene_count": gene_count,
    }
