"""NUMT (Nuclear Mitochondrial DNA Segment) detection.

Detects mitochondrial DNA fragments inserted into the nuclear genome
using BLAST comparison, classifies them by integrity, and visualizes
their distribution on nuclear chromosome ideograms via RIdeogram.
"""

from .detector import (
    NUMTRegion,
    NUMTResult,
    detect_numts,
    write_numt_output,
)
from .visualize import plot_all_numt

__all__ = [
    "NUMTRegion",
    "NUMTResult",
    "detect_numts",
    "write_numt_output",
    "plot_all_numt",
]
