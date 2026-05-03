"""ML-based CMS scorer for inference."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np

from ..features.extractor import CMSFeatureExtractor
from ..predictor import CMSCandidate

logger = logging.getLogger(__name__)


try:
    from sklearn.base import BaseEstimator
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    BaseEstimator = object  # type: ignore

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False


class MLCMSScorer:
    """Score CMS candidates using a trained ML model.

    Supports:
      - Tier 1: LogisticRegression + StandardScaler
      - Tier 2: LightGBM (optionally with classical + pLM features)
      - Tier 3: RandomForest
    """

    def __init__(self, model_path: Path | None = None):
        self.model: Optional[BaseEstimator] = None
        self.scaler: Optional[BaseEstimator] = None
        self.feature_names: list[str] = []
        self.model_type: str = "logreg"  # "logreg" or "lgbm"
        self.extractor = CMSFeatureExtractor()
        if model_path:
            self.load(model_path)

    def load(self, model_path: Path) -> None:
        """Load model artifacts from directory."""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for ML CMS scoring")

        import joblib

        logreg_file = model_path / "cms_logreg.joblib"
        lgbm_file = model_path / "cms_lgbm.joblib"
        rf_file = model_path / "cms_rf.joblib"
        scaler_file = model_path / "cms_scaler.joblib"
        names_file = model_path / "feature_names.json"
        type_file = model_path / "model_type.json"

        if type_file.exists():
            with open(type_file) as f:
                self.model_type = json.load(f).get("model_type", "logreg")

        if self.model_type == "lgbm":
            if not lgbm_file.exists():
                raise FileNotFoundError(f"LightGBM model file not found: {lgbm_file}")
            self.model = joblib.load(lgbm_file)
        elif self.model_type == "rf":
            if not rf_file.exists():
                raise FileNotFoundError(f"RF model file not found: {rf_file}")
            self.model = joblib.load(rf_file)
        else:
            if not logreg_file.exists():
                raise FileNotFoundError(f"Model file not found: {logreg_file}")
            self.model = joblib.load(logreg_file)

        if scaler_file.exists():
            self.scaler = joblib.load(scaler_file)

        if names_file.exists():
            with open(names_file) as f:
                self.feature_names = json.load(f)

        logger.info("Loaded %s ML CMS scorer from %s", self.model_type, model_path)

    def save(self, model_path: Path) -> None:
        """Save model artifacts to directory."""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for ML CMS scoring")

        import joblib

        model_path.mkdir(parents=True, exist_ok=True)
        if self.model is not None:
            if self.model_type == "lgbm":
                joblib.dump(self.model, model_path / "cms_lgbm.joblib")
            elif self.model_type == "rf":
                joblib.dump(self.model, model_path / "cms_rf.joblib")
            else:
                joblib.dump(self.model, model_path / "cms_logreg.joblib")
        if self.scaler is not None:
            joblib.dump(self.scaler, model_path / "cms_scaler.joblib")
        with open(model_path / "feature_names.json", "w") as f:
            json.dump(self.feature_names, f)
        with open(model_path / "model_type.json", "w") as f:
            json.dump({"model_type": self.model_type}, f)
        logger.info("Saved %s ML CMS scorer to %s", self.model_type, model_path)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str] | None = None,
        model_type: str = "logreg",
    ) -> None:
        """Fit scaler and model on training data.

        X: (n_samples, n_features) numpy array
        y: (n_samples,) binary labels
        model_type: "logreg" or "lgbm"
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for ML CMS scoring")

        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler

        self.model_type = model_type
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        if model_type == "rf":
            from sklearn.ensemble import RandomForestClassifier
            self.model = RandomForestClassifier(
                n_estimators=200, max_depth=10, random_state=42, class_weight="balanced"
            )
            self.model.fit(X_scaled, y)
        elif model_type == "lgbm":
            if not LIGHTGBM_AVAILABLE:
                raise ImportError("lightgbm is required for Tier 2 CMS scoring")
            self.model = lgb.LGBMClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=-1,
                num_leaves=31,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
                verbosity=-1,
            )
            self.model.fit(X_scaled, y)
        else:
            self.model = LogisticRegression(max_iter=1000, class_weight="balanced")
            self.model.fit(X_scaled, y)

        if feature_names:
            self.feature_names = feature_names
        else:
            self.feature_names = [f"f{i}" for i in range(X.shape[1])]

    def _vectorize(self, features: dict[str, float]) -> np.ndarray:
        """Convert feature dict to numpy vector."""
        if not self.feature_names:
            return np.array(list(features.values()), dtype=np.float32)
        vec = np.array([features.get(name, 0.0) for name in self.feature_names], dtype=np.float32)
        return vec

    def score_candidate(
        self,
        candidate: CMSCandidate,
        annotated_genes: list | None = None,
        genome_length: int = 0,
    ) -> float:
        """Return ML probability score (0-100)."""
        if self.model is None or self.scaler is None:
            logger.warning("ML scorer not fitted/loaded; returning 0.0")
            return 0.0

        features = self.extractor.extract(candidate, annotated_genes, genome_length)
        vec = self._vectorize(features).reshape(1, -1)
        vec_scaled = self.scaler.transform(vec)
        prob = self.model.predict_proba(vec_scaled)[0, 1]
        return float(prob * 100.0)

    def feature_importance(self) -> dict[str, float]:
        """Return feature importance.

        For logistic regression: coefficients.
        For LightGBM: built-in feature importances.
        """
        if self.model is None or not self.feature_names:
            return {}
        if hasattr(self.model, "coef_"):
            coefs = self.model.coef_[0]
            return {
                name: float(coef)
                for name, coef in zip(self.feature_names, coefs)
            }
        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
            return {
                name: float(imp)
                for name, imp in zip(self.feature_names, importances)
            }
        return {}
