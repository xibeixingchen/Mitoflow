"""Codon usage analysis for mitochondrial genomes."""

from .analysis import (
    CodonUsageResult, analyze_codon_usage,
    calculate_enc_expected, write_codon_tables,
)

__all__ = [
    "CodonUsageResult", "analyze_codon_usage",
    "calculate_enc_expected", "write_codon_tables",
]
