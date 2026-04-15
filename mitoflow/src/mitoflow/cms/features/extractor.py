"""CMS feature extraction orchestrator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .chimera import extract_chimera_features
from .context import extract_context_features
from .homology import extract_homology_features
from .plm import PLMFeatureExtractor
from .sequence import extract_sequence_features

if TYPE_CHECKING:
    from ...models.gene import GeneAnnotation
    from ..predictor import CMSCandidate

logger = logging.getLogger(__name__)


class CMSFeatureExtractor:
    """Extract a feature vector from a CMSCandidate."""

    def __init__(self, use_plm: bool = False, plm_model_path: str | None = None):
        self.use_plm = use_plm
        self.plm_extractor = (
            PLMFeatureExtractor(model_path=plm_model_path) if use_plm else None
        )

    def extract(
        self,
        candidate: CMSCandidate,
        annotated_genes: list[GeneAnnotation] | None = None,
        genome_length: int = 0,
    ) -> dict[str, float]:
        """Return a flat dictionary of features.

        Args:
            candidate: The CMS candidate ORF.
            annotated_genes: List of annotated genes for context features.
            genome_length: Genome length for circular distance calculations.
        """
        features: dict[str, float] = {}
        features.update(extract_sequence_features(candidate))
        features.update(extract_chimera_features(candidate))
        features.update(extract_homology_features(candidate))
        if annotated_genes is not None and genome_length > 0:
            features.update(
                extract_context_features(candidate, annotated_genes, genome_length)
            )
        else:
            features.update({
                "dist_to_nearest_gene": 0.0,
                "n_nearby_5kb": 0.0,
                "has_proximal_boost": 0.0,
                "nearest_is_proximal": 0.0,
            })
        if self.plm_extractor is not None:
            features.update(self.plm_extractor.extract(candidate))
        return features
