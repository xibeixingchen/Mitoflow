#!/usr/bin/env python3
"""End-to-end validation comparing heuristic, Tier 1 ML, and Tier 2 ML CMS scorers."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mitoflow.cms.benchmark.dataset import build_full_dataset
from mitoflow.cms.benchmark.evaluate import evaluate_predictor
from mitoflow.cms.ml.train import train_cms_scorer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _format_row(name: str, metrics: dict) -> str:
    return (
        f"{name:12s}  "
        f"P@1={metrics['precision_at_1']:.3f}  "
        f"P@5={metrics['precision_at_5']:.3f}  "
        f"R@1={metrics['recall_at_1']:.3f}  "
        f"MRR={metrics['mrr']:.3f}  "
        f"AUC={metrics['auc_roc']:.3f}"
    )


def main():
    parser = argparse.ArgumentParser(description="Validate CMS ML scorers against heuristic baseline")
    parser.add_argument("-o", "--output", default="results/cms_validation", help="Output directory")
    parser.add_argument("--n-shuffled", type=int, default=1)
    parser.add_argument("--n-pcg", type=int, default=100)
    parser.add_argument("--n-random", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-tier-2", action="store_true", help="Skip Tier 2 LightGBM validation")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Building validation dataset...")
    dataset = build_full_dataset(
        n_shuffled=args.n_shuffled,
        n_pcg=args.n_pcg,
        n_random=args.n_random,
        seed=args.seed,
    )
    print(f"Dataset: {len(dataset)} samples")

    results: dict[str, dict] = {}

    # 1. Heuristic baseline
    print("\n[1/3] Evaluating heuristic baseline...")
    heuristic_result = evaluate_predictor(dataset)
    results["heuristic"] = heuristic_result.to_dict()
    print(_format_row("Heuristic", results["heuristic"]))

    # 2. Tier 1 Logistic Regression
    print("\n[2/3] Training Tier 1 (Logistic Regression)...")
    tier1_dir = output_dir / "models_tier1"
    try:
        train_cms_scorer(
            output_dir=tier1_dir,
            n_shuffled=args.n_shuffled,
            n_pcg=args.n_pcg,
            n_random=args.n_random,
            seed=args.seed,
            tier=1,
            use_plm=False,
        )
        tier1_result = evaluate_predictor(
            dataset,
            use_ml_scorer=True,
            ml_scorer_path=tier1_dir,
            score_key="ml_confidence",
        )
        results["tier1_logreg"] = tier1_result.to_dict()
        print(_format_row("Tier1-LogReg", results["tier1_logreg"]))
    except Exception as e:
        logger.warning("Tier 1 validation failed: %s", e)
        results["tier1_logreg"] = {"error": str(e)}

    # 3. Tier 2 LightGBM
    if not args.skip_tier_2:
        print("\n[3/3] Training Tier 2 (LightGBM)...")
        tier2_dir = output_dir / "models_tier2"
        try:
            train_cms_scorer(
                output_dir=tier2_dir,
                n_shuffled=args.n_shuffled,
                n_pcg=args.n_pcg,
                n_random=args.n_random,
                seed=args.seed,
                tier=2,
                use_plm=False,
            )
            tier2_result = evaluate_predictor(
                dataset,
                use_ml_scorer=True,
                ml_scorer_path=tier2_dir,
                score_key="ml_confidence",
            )
            results["tier2_lgbm"] = tier2_result.to_dict()
            print(_format_row("Tier2-LightGBM", results["tier2_lgbm"]))
        except Exception as e:
            logger.warning("Tier 2 validation failed: %s", e)
            results["tier2_lgbm"] = {"error": str(e)}
    else:
        results["tier2_lgbm"] = {"skipped": True}

    # Save JSON report
    json_path = output_dir / "validation_report.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    # Save text report
    lines = [
        "=== CMS Scorer Validation Report ===",
        "",
        _format_row("Heuristic", results["heuristic"]),
    ]
    if "error" not in results.get("tier1_logreg", {}):
        lines.append(_format_row("Tier1-LogReg", results["tier1_logreg"]))
    if "error" not in results.get("tier2_lgbm", {}) and "skipped" not in results.get("tier2_lgbm", {}):
        lines.append(_format_row("Tier2-LightGBM", results["tier2_lgbm"]))
    lines.append(f"\nReport saved to: {output_dir}")

    txt_path = output_dir / "validation_report.txt"
    txt_path.write_text("\n".join(lines))
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
