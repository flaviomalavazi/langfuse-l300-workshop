"""End-to-end pairwise LLM-as-a-judge pipeline.

Runs:
  1. seed dataset (idempotent)
  2. generate System A run on the dataset
  3. generate System B run on the dataset
  4. judge each (A, B) pair with two-pass swap mitigation
  5. aggregate win/tie/loss and write run-level scores back to Langfuse

Usage:
  uv run python run_pipeline.py
"""

from __future__ import annotations

import time

from langfuse import get_client

from pairwise_judge.aggregate import attach_run_scores, format_report, summarize
from pairwise_judge.config import Config
from pairwise_judge.experiments import run_candidate_experiment, run_pairwise_judge
from pairwise_judge.seed_dataset import seed


def main() -> None:
    cfg = Config.from_env()
    seed(cfg)

    suffix = time.strftime("%Y%m%d-%H%M%S")
    run_a = run_candidate_experiment(cfg, "A", run_suffix=suffix)
    run_b = run_candidate_experiment(cfg, "B", run_suffix=suffix)

    print(f"[judge] {len(run_a.outputs)} pairs with judge={cfg.judge_model}")
    decisions = run_pairwise_judge(cfg, run_a, run_b)

    summary = summarize(decisions)
    attach_run_scores(run_a, run_b, summary)

    print()
    print(format_report(run_a, run_b, summary))

    get_client().flush()


if __name__ == "__main__":
    main()
