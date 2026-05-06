"""Tests for CMS ML scorer."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

sklearn = pytest.importorskip("sklearn")

from mitoflow.cms.ml.scorer import LIGHTGBM_AVAILABLE, MLCMSScorer


def test_ml_module_imports():
    """Ensure ML subpackage can be imported."""
    from mitoflow.cms import ml

    assert ml is not None


def test_logreg_scorer_fit_and_predict():
    """Tier 1 Logistic Regression scorer should fit and produce probabilities."""
    X = np.random.randn(30, 4).astype(np.float32)
    y = np.array([0] * 15 + [1] * 15, dtype=np.int32)

    scorer = MLCMSScorer()
    scorer.fit(X, y, feature_names=["f1", "f2", "f3", "f4"], model_type="logreg")

    assert scorer.model_type == "logreg"
    assert scorer.model is not None
    assert scorer.scaler is not None

    probs = scorer.model.predict_proba(scorer.scaler.transform(X[:3]))[:, 1]
    assert (probs >= 0).all() and (probs <= 1).all()

    importance = scorer.feature_importance()
    assert set(importance.keys()) == {"f1", "f2", "f3", "f4"}


def test_logreg_scorer_save_and_load():
    """Tier 1 scorer should persist and reload correctly."""
    X = np.random.randn(20, 3).astype(np.float32)
    y = np.array([0] * 10 + [1] * 10, dtype=np.int32)

    scorer = MLCMSScorer()
    scorer.fit(X, y, feature_names=["a", "b", "c"], model_type="logreg")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        scorer.save(path)
        assert (path / "cms_logreg.joblib").exists()
        assert (path / "feature_names.json").exists()

        loaded = MLCMSScorer(path)
        assert loaded.model_type == "logreg"
        assert loaded.feature_names == ["a", "b", "c"]
        vec = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        prob1 = scorer.model.predict_proba(scorer.scaler.transform(vec))[:, 1]
        prob2 = loaded.model.predict_proba(loaded.scaler.transform(vec))[:, 1]
        assert np.allclose(prob1, prob2)


def test_lgbm_scorer_fit_and_predict():
    """Tier 2 LightGBM scorer should fit and produce probabilities if available."""
    if not LIGHTGBM_AVAILABLE:
        return

    X = np.random.randn(30, 4).astype(np.float32)
    y = np.array([0] * 15 + [1] * 15, dtype=np.int32)

    scorer = MLCMSScorer()
    scorer.fit(X, y, feature_names=["f1", "f2", "f3", "f4"], model_type="lgbm")

    assert scorer.model_type == "lgbm"
    assert scorer.model is not None

    probs = scorer.model.predict_proba(scorer.scaler.transform(X[:3]))[:, 1]
    assert (probs >= 0).all() and (probs <= 1).all()

    importance = scorer.feature_importance()
    assert set(importance.keys()) == {"f1", "f2", "f3", "f4"}


def test_lgbm_scorer_save_and_load():
    """Tier 2 scorer should persist and reload correctly if available."""
    if not LIGHTGBM_AVAILABLE:
        return

    X = np.random.randn(20, 3).astype(np.float32)
    y = np.array([0] * 10 + [1] * 10, dtype=np.int32)

    scorer = MLCMSScorer()
    scorer.fit(X, y, feature_names=["a", "b", "c"], model_type="lgbm")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        scorer.save(path)
        assert (path / "cms_lgbm.joblib").exists()
        assert (path / "model_type.json").exists()

        loaded = MLCMSScorer(path)
        assert loaded.model_type == "lgbm"
        assert loaded.feature_names == ["a", "b", "c"]
