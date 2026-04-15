"""Genomic context features for CMS candidates."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models.gene import GeneAnnotation
    from ..predictor import CMSCandidate


# CMS-associated genes whose proximity boosts likelihood
_PROXIMAL_GENES = {
    "atp1", "atp4", "atp6", "atp8", "atp9",
    "cox1", "cox2", "cox3", "cob",
}


def extract_context_features(
    candidate: "CMSCandidate",
    annotated_genes: list[GeneAnnotation],
    genome_length: int,
) -> dict[str, float]:
    """Extract genomic context features.

    Returns:
        Dict with keys: dist_to_nearest_gene, n_nearby_5kb,
        has_proximal_boost, nearest_is_proximal.
    """
    if not annotated_genes:
        return {
            "dist_to_nearest_gene": float(genome_length),
            "n_nearby_5kb": 0.0,
            "has_proximal_boost": 0.0,
            "nearest_is_proximal": 0.0,
        }

    min_dist = genome_length
    n_nearby = 0
    has_proximal = False
    nearest_is_proximal = False

    for ann in annotated_genes:
        # Distance from candidate region to gene region
        if candidate.start <= ann.genomic_end and ann.genomic_start <= candidate.end:
            dist = 0
        else:
            dist = min(
                abs(candidate.start - ann.genomic_end),
                abs(candidate.end - ann.genomic_start),
            )
            # Circular wrap-around
            dist = min(dist, genome_length - dist)

        if dist < min_dist:
            min_dist = dist
            nearest_is_proximal = ann.gene_name.lower() in _PROXIMAL_GENES

        if dist <= 5000:
            n_nearby += 1
            if ann.gene_name.lower() in _PROXIMAL_GENES:
                has_proximal = True

    return {
        "dist_to_nearest_gene": float(min_dist),
        "n_nearby_5kb": float(n_nearby),
        "has_proximal_boost": 1.0 if has_proximal else 0.0,
        "nearest_is_proximal": 1.0 if nearest_is_proximal else 0.0,
    }
