"""Tests for CMS feature extraction."""

from __future__ import annotations

from dataclasses import dataclass

from mitoflow.cms.features.extractor import CMSFeatureExtractor
from mitoflow.cms.features.plm import PLMFeatureExtractor, extract_plm_features


def _make_fake_candidate(protein_seq: str = "MKTLLILLLPL"):
    from mitoflow.cms.predictor import CMSCandidate
    return CMSCandidate(
        orf_id="test_orf",
        start=1,
        end=100,
        strand=1,
        length_aa=len(protein_seq),
        protein_seq=protein_seq,
    )


def test_feature_module_imports():
    """Ensure feature subpackage can be imported."""
    from mitoflow.cms import features

    assert features is not None


def test_extractor_returns_classical_features():
    """CMSFeatureExtractor should return classical features without pLM."""
    extractor = CMSFeatureExtractor(use_plm=False)
    features = extractor.extract(_make_fake_candidate(), annotated_genes=[], genome_length=1000)
    assert "length_aa" in features
    assert "gravy" in features
    assert "n_chimera_sources" in features
    assert "has_cms_homolog" in features
    # No ESM-2 keys when use_plm=False
    assert not any(k.startswith("esm2_") for k in features)


def test_plm_fallback_when_model_missing():
    """PLMFeatureExtractor should gracefully fall back to zeros."""
    extractor = PLMFeatureExtractor(model_path="/nonexistent/path")
    assert extractor.available is False
    features = extractor.extract(_make_fake_candidate())
    assert len(features) == 320
    assert all(v == 0.0 for v in features.values())
    assert all(k.startswith("esm2_") for k in features)


def test_extract_plm_features_wrapper():
    """Convenience wrapper should also fall back gracefully."""
    features = extract_plm_features(_make_fake_candidate(), model_path="/nonexistent/path")
    assert len(features) == 320
    assert all(v == 0.0 for v in features.values())
