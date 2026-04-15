#!/usr/bin/env python3
"""Run CMS predictor benchmark and report baseline metrics."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mitoflow.cms.benchmark.dataset import build_full_dataset
from mitoflow.cms.benchmark.evaluate import evaluate_predictor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def main():
    parser = argparse.ArgumentParser(description="Benchmark CMS predictor baseline")
    parser.add_argument("-o", "--output", default="results/cms_benchmark", help="Output directory")
    parser.add_argument("--n-shuffled", type=int, default=1, help="Shuffled negatives per positive")
    parser.add_argument("--n-pcg", type=int, default=100, help="Number of PCG negatives")
    parser.add_argument("--n-random", type=int, default=100, help="Number of random ORF negatives")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Building benchmark dataset...")
    dataset = build_full_dataset(
        n_shuffled=args.n_shuffled,
        n_pcg=args.n_pcg,
        n_random=args.n_random,
        seed=args.seed,
    )

    print(f"Dataset: {len(dataset)} samples")
    print("Running predictor (this may take a while)...")
    result = evaluate_predictor(dataset)

    # Save JSON
    json_path = output_dir / "benchmark_results.json"
    with open(json_path, "w") as f:
        json.dump(
            {
                "metrics": result.to_dict(),
                "per_sample": result.per_sample_results,
            },
            f,
            indent=2,
        )

    # Save text report
    report_path = output_dir / "benchmark_report.txt"
    report_path.write_text(result.summary())

    print(result.summary())
    print(f"\nResults saved to: {output_dir}")


if __name__ == "__main__":
    main()
