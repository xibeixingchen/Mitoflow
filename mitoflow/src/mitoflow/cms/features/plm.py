"""Protein language model (ESM-2) feature extraction for CMS candidates."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ..predictor import CMSCandidate

logger = logging.getLogger(__name__)


try:
    import torch
    from transformers import EsmModel, EsmTokenizer
    _TRANSFORMERS_AVAILABLE = True
except Exception as e:
    _TRANSFORMERS_AVAILABLE = False
    logger.debug("transformers/torch not available for pLM features: %s", e)


# Default local model path (bundled or manually downloaded)
_DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "data" / "cms" / "models" / "esm2_t6_8M_UR50D"


class PLMFeatureExtractor:
    """Lazy-loading ESM-2 feature extractor.

    Falls back gracefully if dependencies or local model weights are missing.
    """

    def __init__(self, model_path: Path | str | None = None):
        self.model_path = Path(model_path) if model_path else _DEFAULT_MODEL_PATH
        self._tokenizer = None
        self._model = None
        self._available: bool | None = None
        self._embedding_dim: int = 0

    def _load(self) -> bool:
        """Attempt to load tokenizer and model from local path."""
        if self._available is not None:
            return self._available

        if not _TRANSFORMERS_AVAILABLE:
            self._available = False
            return False

        if not self.model_path.exists():
            logger.warning(
                "ESM-2 model not found at %s; pLM features will be disabled. "
                "Download with: transformers-cli download facebook/esm2_t6_8M_UR50D --cache-dir ...",
                self.model_path,
            )
            self._available = False
            return False

        try:
            self._tokenizer = EsmTokenizer.from_pretrained(str(self.model_path))
            self._model = EsmModel.from_pretrained(str(self.model_path))
            self._model.eval()
            # Infer embedding dimension from model config
            self._embedding_dim = int(getattr(self._model.config, "hidden_size", 320))
            self._available = True
            logger.info("Loaded ESM-2 model from %s (dim=%d)", self.model_path, self._embedding_dim)
        except Exception as e:
            logger.warning("Failed to load ESM-2 model: %s", e)
            self._available = False

        return self._available

    @property
    def available(self) -> bool:
        return self._load()

    @property
    def embedding_dim(self) -> int:
        self._load()
        return self._embedding_dim

    def extract(self, candidate: "CMSCandidate") -> dict[str, float]:
        """Return ESM-2 embedding as a flat dictionary.

        If model is unavailable, returns an all-zero dict with the expected keys.
        """
        if not self._load():
            dim = 320  # default fallback dimension for esm2_t6_8M
            return {f"esm2_d{i}": 0.0 for i in range(dim)}

        seq = candidate.protein_seq.upper()
        if not seq:
            return {f"esm2_d{i}": 0.0 for i in range(self._embedding_dim)}

        try:
            inputs = self._tokenizer(  # type: ignore
                seq,
                return_tensors="pt",
                truncation=True,
                max_length=1024,
            )
            with torch.no_grad():
                outputs = self._model(**inputs)  # type: ignore
            # Mean pooling over sequence length (exclude special tokens implicitly)
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
        except Exception as e:
            logger.warning("ESM-2 inference failed: %s", e)
            return {f"esm2_d{i}": 0.0 for i in range(self._embedding_dim)}

        vec = np.asarray(embedding, dtype=np.float32).flatten()
        if vec.shape[0] != self._embedding_dim:
            # Pad or truncate to expected dimension
            padded = np.zeros(self._embedding_dim, dtype=np.float32)
            padded[: min(vec.shape[0], self._embedding_dim)] = vec[: min(vec.shape[0], self._embedding_dim)]
            vec = padded

        return {f"esm2_d{i}": float(v) for i, v in enumerate(vec)}


def extract_plm_features(candidate: "CMSCandidate", model_path: Path | str | None = None) -> dict[str, float]:
    """Convenience wrapper for one-off ESM-2 feature extraction."""
    extractor = PLMFeatureExtractor(model_path=model_path)
    return extractor.extract(candidate)
