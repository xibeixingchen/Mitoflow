"""Multi-configuration structure analysis."""

from .repeat_mediated import (
    RepeatPair, SubgenomicCircle, MulticonfResult,
    predict_subgenomes, verify_recombination_with_longreads,
)

__all__ = [
    "RepeatPair", "SubgenomicCircle", "MulticonfResult",
    "predict_subgenomes", "verify_recombination_with_longreads",
]
