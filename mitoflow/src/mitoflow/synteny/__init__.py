"""Synteny (gene order collinearity) analysis and visualisation."""

from .collinear import (
    SyntenyBlock,
    SyntenyResult,
    detect_synteny,
    write_synteny_tables,
)
from .visualize import (
    SyntenyVizConfig,
    draw_synteny,
    draw_pairwise_synteny,
    draw_gene_order_heatmap,
    draw_synteny_gbdraw,
    check_gbdraw_available,
)

__all__ = [
    # Core analysis
    "SyntenyBlock",
    "SyntenyResult",
    "detect_synteny",
    "write_synteny_tables",
    # Visualisation
    "SyntenyVizConfig",
    "draw_synteny",
    "draw_pairwise_synteny",
    "draw_gene_order_heatmap",
    "draw_synteny_gbdraw",
    "check_gbdraw_available",
]
