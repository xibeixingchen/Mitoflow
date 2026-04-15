"""Benchmark runner for CMS predictor."""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..predictor import predict_cms
from .dataset import CMSTestSample
from .synthetic_genomes import build_synthetic_genome

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Results of a CMS benchmark run."""

    n_samples: int = 0
    n_positives: int = 0
    n_negatives: int = 0
    precision_at_1: float = 0.0
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    precision_at_20: float = 0.0
    recall_at_1: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    recall_at_20: float = 0.0
    mrr: float = 0.0
    auc_roc: float = 0.0
    per_sample_results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "n_samples": self.n_samples,
            "n_positives": self.n_positives,
            "n_negatives": self.n_negatives,
            "precision_at_1": self.precision_at_1,
            "precision_at_5": self.precision_at_5,
            "precision_at_10": self.precision_at_10,
            "precision_at_20": self.precision_at_20,
            "recall_at_1": self.recall_at_1,
            "recall_at_5": self.recall_at_5,
            "recall_at_10": self.recall_at_10,
            "recall_at_20": self.recall_at_20,
            "mrr": self.mrr,
            "auc_roc": self.auc_roc,
        }

    def summary(self) -> str:
        lines = [
            "=== CMS Predictor Benchmark ===",
            f"Samples: {self.n_samples} ({self.n_positives} pos, {self.n_negatives} neg)",
            f"Precision@1:  {self.precision_at_1:.3f}",
            f"Precision@5:  {self.precision_at_5:.3f}",
            f"Precision@10: {self.precision_at_10:.3f}",
            f"Precision@20: {self.precision_at_20:.3f}",
            f"Recall@1:     {self.recall_at_1:.3f}",
            f"Recall@5:     {self.recall_at_5:.3f}",
            f"Recall@10:    {self.recall_at_10:.3f}",
            f"Recall@20:    {self.recall_at_20:.3f}",
            f"MRR:          {self.mrr:.3f}",
            f"AUC-ROC:      {self.auc_roc:.3f}",
        ]
        return "\n".join(lines)


def evaluate_predictor(
    dataset: list[CMSTestSample],
    min_orf_length: int = 300,
    max_candidates: int = 50,
    use_ml_scorer: bool = False,
    ml_scorer_path: Optional[Path] = None,
    use_plm: bool = False,
    plm_model_path: Optional[Path] = None,
    score_key: str = "total_score",
) -> BenchmarkResult:
    """Run the CMS predictor against the benchmark dataset.

    Args:
        dataset: List of CMSTestSample.
        min_orf_length: Minimum ORF length in bp.
        max_candidates: Maximum candidates to report.
        use_ml_scorer: Whether to enable ML-based scoring.
        ml_scorer_path: Path to trained model directory.
        use_plm: Whether to use pLM features with ML scorer.
        plm_model_path: Local path to ESM-2 model.
        score_key: Candidate attribute to use as score ("total_score" or "ml_confidence").

    Returns:
        BenchmarkResult with metrics.
    """
    result = BenchmarkResult()
    result.n_samples = len(dataset)
    result.n_positives = sum(1 for s in dataset if s.label == 1)
    result.n_negatives = sum(1 for s in dataset if s.label == 0)

    scores: list[float] = []
    labels: list[int] = []
    reciprocal_ranks: list[float] = []
    hits_at_k: dict[int, list[int]] = {1: [], 5: [], 10: [], 20: []}

    for sample in dataset:
        genome_seq, annotated_genes, test_coords = build_synthetic_genome(sample)
        test_start, test_end = test_coords
        test_len = test_end - test_start + 1

        with tempfile.TemporaryDirectory() as tmpdir:
            fasta_path = Path(tmpdir) / "genome.fasta"
            fasta_path.write_text(f">{sample.sample_id}\n{genome_seq}\n")

            cms_result = predict_cms(
                fasta_path=fasta_path,
                genome_seq=genome_seq,
                annotated_genes=annotated_genes,
                gene_protein_db=None,
                threads=1,
                min_orf_length=min_orf_length,
                max_candidates=max_candidates,
                use_ml_scorer=use_ml_scorer,
                ml_scorer_path=ml_scorer_path,
                use_plm=use_plm,
                plm_model_path=plm_model_path,
            )

            # Find the rank of the candidate that overlaps the embedded test ORF
            rank: Optional[int] = None
            for idx, cand in enumerate(cms_result.candidates, start=1):
                overlap_start = max(cand.start, test_start)
                overlap_end = min(cand.end, test_end)
                overlap_len = max(0, overlap_end - overlap_start + 1)
                if overlap_len / test_len >= 0.5:
                    rank = idx
                    break

            if rank is None:
                rank = 9999
                score = 0.0
            else:
                cand = cms_result.candidates[rank - 1]
                score = getattr(cand, score_key, cand.total_score)

            scores.append(score)
            labels.append(sample.label)
            rr = 1.0 / rank if rank <= max_candidates else 0.0
            reciprocal_ranks.append(rr)

            for k in hits_at_k:
                hits_at_k[k].append(1 if rank <= k else 0)

            result.per_sample_results.append({
                "sample_id": sample.sample_id,
                "label": sample.label,
                "source_type": sample.source_type,
                "rank": rank if rank <= max_candidates else None,
                "score": score,
                "reciprocal_rank": rr,
                "n_candidates": cms_result.n_candidates,
            })

    # Compute metrics
    for k in hits_at_k:
        setattr(result, f"precision_at_{k}", _precision(hits_at_k[k], labels))
        setattr(result, f"recall_at_{k}", _recall(hits_at_k[k], labels))

    result.mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
    result.auc_roc = _compute_auc_roc(scores, labels)

    return result


def _precision(hits: list[int], labels: list[int]) -> float:
    """Precision = TP / (TP + FP) approximated by mean of hits / k."""
    if not hits:
        return 0.0
    return sum(hits) / len(hits)


def _recall(hits: list[int], labels: list[int]) -> float:
    """Recall@K = fraction of positives that were hit."""
    positives = [h for h, l in zip(hits, labels) if l == 1]
    if not positives:
        return 0.0
    return sum(positives) / len(positives)


def _compute_auc_roc(scores: list[float], labels: list[int]) -> float:
    """Compute AUC-ROC from scores and binary labels."""
    try:
        from sklearn.metrics import roc_auc_score

        # Normalize scores to [0, 1] by dividing by 100 (heuristic max)
        norm_scores = [min(1.0, max(0.0, s / 100.0)) for s in scores]
        return float(roc_auc_score(labels, norm_scores))
    except ImportError:
        logger.warning("sklearn not installed; AUC-ROC will be computed with a manual fallback")
        return _manual_auc_roc(scores, labels)


def _manual_auc_roc(scores: list[float], labels: list[int]) -> float:
    """Simple trapezoidal AUC-ROC fallback."""
    pairs = sorted(zip(scores, labels), key=lambda x: x[0], reverse=True)
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5

    tp = 0
    fp = 0
    prev_score = None
    prev_fp = 0
    auc = 0.0
    for score, label in pairs:
        if prev_score is not None and score != prev_score:
            auc += tp * (fp - prev_fp)
            prev_fp = fp
        if label == 1:
            tp += 1
        else:
            fp += 1
        prev_score = score
    # Final rectangle
    auc += tp * (fp - prev_fp)
    return auc / (n_pos * n_neg)
