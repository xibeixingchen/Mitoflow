"""Continuous CMS homology features for CMS candidates."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..predictor import CMSCandidate


def extract_homology_features(candidate: "CMSCandidate") -> dict[str, float]:
    """Extract continuous homology features against known CMS genes.

    Returns:
        Dict with keys: has_cms_homolog, cms_identity, cms_homolog_score.
    """
    has_homolog = 1.0 if candidate.cms_homolog else 0.0
    identity = candidate.cms_identity
    # A simple continuous score: identity if hit exists, otherwise 0
    score = identity if has_homolog else 0.0

    return {
        "has_cms_homolog": has_homolog,
        "cms_identity": identity,
        "cms_homolog_score": score,
    }
