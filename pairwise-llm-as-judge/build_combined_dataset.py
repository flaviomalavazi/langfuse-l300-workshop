"""Build a combined Langfuse dataset for UI-driven pairwise evaluation.

Runs:
  1. seed source dataset (idempotent)
  2. generate System A run on the source dataset
  3. generate System B run on the source dataset
  4. write a new dataset (default: '<source>-combined') whose items each
     contain the original question plus both responses, ordered with model
     metadata first

After this completes, configure an LLM-as-a-Judge evaluator in the Langfuse
UI (see evaluator_prompt.md) and run it against the combined dataset.

Usage:
  uv run python build_combined_dataset.py
"""

from __future__ import annotations

import time

from langfuse import get_client

from pairwise_judge.combined_dataset import build_combined_dataset
from pairwise_judge.config import Config
from pairwise_judge.experiments import run_candidate_experiment
from pairwise_judge.seed_dataset import seed


def main() -> None:
    cfg = Config.from_env()
    seed(cfg)

    suffix = time.strftime("%Y%m%d-%H%M%S")
    run_a = run_candidate_experiment(cfg, "A", run_suffix=suffix)
    run_b = run_candidate_experiment(cfg, "B", run_suffix=suffix)

    combined_name = build_combined_dataset(cfg, run_a, run_b)

    print()
    print(f"Combined dataset ready: {combined_name}")
    print("Next steps in the Langfuse UI:")
    print("  1. Datasets -> open the combined dataset to inspect items.")
    print("  2. Evaluators -> New evaluator -> LLM-as-a-Judge.")
    print("     Use the prompt template from evaluator_prompt.md and map:")
    print("       question    -> input.question")
    print("       response_a  -> input.response_a")
    print("       response_b  -> input.response_b")
    print("       model_a     -> input.model_a")
    print("       model_b     -> input.model_b")
    print("  3. Attach the evaluator to the combined dataset and run.")

    get_client().flush()


if __name__ == "__main__":
    main()
