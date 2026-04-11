"""RNA editing prediction for plant mitochondrial genomes."""

from .predictor import (
    EditingSite, EditingResult,
    predict_editing_by_homology, predict_editing_from_known_sites,
    correct_protein_with_editing, build_editing_result,
)
from .corrector import (
    correct_genbank_proteins,
    write_corrected_fasta,
    generate_editing_vcf,
    plot_editing_summary,
)

__all__ = [
    # predictor
    "EditingSite", "EditingResult",
    "predict_editing_by_homology", "predict_editing_from_known_sites",
    "correct_protein_with_editing", "build_editing_result",
    # corrector
    "correct_genbank_proteins",
    "write_corrected_fasta",
    "generate_editing_vcf",
    "plot_editing_summary",
]
