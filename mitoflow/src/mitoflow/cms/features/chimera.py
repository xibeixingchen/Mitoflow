"""Continuous chimera features for CMS candidates."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..predictor import CMSCandidate, ChimeraInfo


def extract_chimera_features(candidate: "CMSCandidate") -> dict[str, float]:
    """Extract continuous chimera features from BLAST results.

    Returns:
        Dict with keys: n_chimera_sources, max_qcov, total_qcov,
        chimera_entropy, chimera_score.
    """
    chimera = candidate.chimera
    if chimera is None or not chimera.source_genes:
        return {
            "n_chimera_sources": 0.0,
            "max_qcov": 0.0,
            "total_qcov": 0.0,
            "chimera_entropy": 0.0,
            "chimera_score": 0.0,
        }

    coverage = chimera.coverage_by_source
    n_sources = len(coverage)
    max_qcov = max(coverage.values()) if coverage else 0.0
    total_qcov = min(100.0, sum(coverage.values()))

    # Shannon entropy of coverage distribution (normalized)
    total = sum(coverage.values())
    entropy = 0.0
    if total > 0:
        for qcov in coverage.values():
            p = qcov / total
            if p > 0:
                entropy -= p * math.log2(p)
        max_ent = math.log2(n_sources) if n_sources > 1 else 1.0
        entropy = entropy / max_ent if max_ent > 0 else 0.0

    return {
        "n_chimera_sources": float(n_sources),
        "max_qcov": max_qcov,
        "total_qcov": total_qcov,
        "chimera_entropy": entropy,
        "chimera_score": chimera.chimera_score * 100.0,
    }
