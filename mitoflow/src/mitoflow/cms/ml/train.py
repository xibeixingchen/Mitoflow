"""Training script for Tier 1/2 CMS ML scorer."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import numpy as np

from ..benchmark.dataset import build_full_dataset
from ..benchmark.synthetic_genomes import build_synthetic_genome
from ..predictor import predict_cms
from ..features.extractor import CMSFeatureExtractor
from .scorer import MLCMSScorer

logger = logging.getLogger(__name__)


def _match_candidate(cms_result, test_start: int, test_end: int) -> "CMSCandidate | None":
    """Find candidate overlapping the embedded test ORF."""
    test_len = test_end - test_start + 1
    for cand in cms_result.candidates:
        overlap_start = max(cand.start, test_start)
        overlap_end = min(cand.end, test_end)
        overlap_len = max(0, overlap_end - overlap_start + 1)
        if overlap_len / test_len >= 0.5:
            return cand
    return None


def train_cms_scorer(
    output_dir: Path,
    n_shuffled: int = 1,
    n_pcg: int = 100,
    n_random: int = 100,
    seed: int = 42,
    tier: int = 1,
    use_plm: bool = False,
    plm_model_path: str | None = None,
) -> MLCMSScorer:
    """Train a Tier 1 (Logistic Regression) or Tier 2 (LightGBM) CMS scorer.

    Returns:
        Fitted MLCMSScorer.
    """
    model_type = "lgbm" if tier == 2 else "rf" if tier == 3 else "logreg"
    if model_type == "lgbm":
        try:
            import lightgbm as lgb  # noqa: F401
        except ImportError as e:
            raise ImportError("lightgbm is required for Tier 2 training") from e

    logger.info("Building training dataset...")
    dataset = build_full_dataset(
        n_shuffled=n_shuffled,
        n_pcg=n_pcg,
        n_random=n_random,
        seed=seed,
    )

    extractor = CMSFeatureExtractor(use_plm=use_plm, plm_model_path=plm_model_path)
    feature_dicts: list[dict[str, float]] = []
    labels: list[int] = []

    logger.info("Extracting features from %d samples (tier=%d, use_plm=%s)...", len(dataset), tier, use_plm)
    for sample in dataset:
        genome_seq, annotated_genes, (test_start, test_end) = build_synthetic_genome(sample)

        with tempfile.TemporaryDirectory() as tmpdir:
            fasta_path = Path(tmpdir) / "genome.fasta"
            fasta_path.write_text(f">{sample.sample_id}\n{genome_seq}\n")

            cms_result = predict_cms(
                fasta_path=fasta_path,
                genome_seq=genome_seq,
                annotated_genes=annotated_genes,
                gene_protein_db=None,
                threads=1,
                min_orf_length=300,
                max_candidates=50,
            )

            cand = _match_candidate(cms_result, test_start, test_end)
            if cand is None:
                logger.debug("Sample %s: no matching candidate found, skipping", sample.sample_id)
                continue

            features = extractor.extract(cand, annotated_genes, len(genome_seq))
            feature_dicts.append(features)
            labels.append(sample.label)

    if len(feature_dicts) < 10:
        raise ValueError(f"Too few training samples after filtering: {len(feature_dicts)}")

    # Align feature names
    all_keys = sorted(feature_dicts[0].keys())
    X = np.array([[fd.get(k, 0.0) for k in all_keys] for fd in feature_dicts], dtype=np.float32)
    y = np.array(labels, dtype=np.int32)

    logger.info("Training set: %d samples, %d features", X.shape[0], X.shape[1])

    # Cross-validation
    aucs: list[float] = []
    precs: list[float] = []
    recs: list[float] = []
    f1s: list[float] = []
    try:
        from sklearn.model_selection import StratifiedKFold
        from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)

        for train_idx, val_idx in cv.split(X, y):
            scorer = MLCMSScorer()
            scorer.fit(X[train_idx], y[train_idx], feature_names=all_keys, model_type=model_type)
            val_probs = scorer.model.predict_proba(scorer.scaler.transform(X[val_idx]))[:, 1]  # type: ignore
            val_preds = (val_probs >= 0.5).astype(int)
            aucs.append(roc_auc_score(y[val_idx], val_probs))
            precs.append(precision_score(y[val_idx], val_preds, zero_division=0))
            recs.append(recall_score(y[val_idx], val_preds, zero_division=0))
            f1s.append(f1_score(y[val_idx], val_preds, zero_division=0))

        logger.info(
            "CV results: AUC=%.3f±%.3f P=%.3f±%.3f R=%.3f±%.3f F1=%.3f±%.3f",
            np.mean(aucs), np.std(aucs),
            np.mean(precs), np.std(precs),
            np.mean(recs), np.std(recs),
            np.mean(f1s), np.std(f1s),
        )
    except Exception as e:
        logger.warning("Cross-validation failed: %s", e)

    # Final model on all data
    final_scorer = MLCMSScorer()
    final_scorer.fit(X, y, feature_names=all_keys, model_type=model_type)

    # Save
    output_dir.mkdir(parents=True, exist_ok=True)
    final_scorer.save(output_dir)

    # Feature importance report
    importance = final_scorer.feature_importance()
    report = {
        "model_type": model_type,
        "feature_importance": dict(sorted(importance.items(), key=lambda x: abs(x[1]), reverse=True)),
        "n_training_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "cv_auc_mean": float(np.mean(aucs)) if aucs else None,
        "cv_auc_std": float(np.std(aucs)) if aucs else None,
    }
    with open(output_dir / "training_report.json", "w") as f:
        json.dump(report, f, indent=2)

    logger.info("Model saved to %s", output_dir)
    return final_scorer


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Train Tier 1/2 CMS ML scorer")
    parser.add_argument("-o", "--output", default="src/mitoflow/data/cms/models", help="Output directory")
    parser.add_argument("--n-shuffled", type=int, default=1)
    parser.add_argument("--n-pcg", type=int, default=100)
    parser.add_argument("--n-random", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tier", type=int, choices=[1, 2], default=1, help="Model tier: 1=LogisticRegression, 2=LightGBM")
    parser.add_argument("--use-plm", action="store_true", help="Include ESM-2 protein language model features")
    parser.add_argument("--plm-model-path", default=None, help="Local path to ESM-2 model directory")
    args = parser.parse_args()

    train_cms_scorer(
        output_dir=Path(args.output),
        n_shuffled=args.n_shuffled,
        n_pcg=args.n_pcg,
        n_random=args.n_random,
        seed=args.seed,
        tier=args.tier,
        use_plm=args.use_plm,
        plm_model_path=args.plm_model_path,
    )
