"""Trigger one SDK-driven run of the pairwise evaluator over the combined dataset.

Equivalent of the UI 'Run Experiment' wizard, expressed entirely via the
Langfuse Python SDK + Anthropic SDK:

  1. ensure_judge_prompt — create / version the chat prompt in Langfuse
     Prompt Management and persist the structured-output schema in its
     config under the key 'pairwise-evaluator-output-schema'.
  2. run_pairwise_evaluator_experiment — fetch the prompt, run it on every
     item of the combined dataset using claude-haiku-4-5-20251001 with
     Anthropic tool-use to enforce the schema, and write categorical scores
     back to each trace.

Prerequisite: a combined dataset already exists. Run
`python build_combined_dataset.py` first if it does not.

Usage:
  uv run python run_pairwise_evaluator.py
"""

from __future__ import annotations

from collections import Counter

from langfuse import get_client

from pairwise_judge.config import Config
from pairwise_judge.ui_evaluator import (
    JUDGE_PROMPT_NAME,
    OUTPUT_SCHEMA_NAME,
    ensure_judge_prompt,
    run_pairwise_evaluator_experiment,
)

MODEL = "claude-haiku-4-5-20251001"


def main() -> None:
    cfg = Config.from_env()
    combined_name = f"{cfg.dataset_name}-combined"

    prompt = ensure_judge_prompt(model=MODEL)
    print(
        f"Prompt '{JUDGE_PROMPT_NAME}' v{prompt.version} ready "
        f"(schema in config['{OUTPUT_SCHEMA_NAME}'])."
    )

    result = run_pairwise_evaluator_experiment(
        cfg, combined_dataset_name=combined_name, model=MODEL
    )

    verdicts: list[str] = []
    winning_models: list[str] = []
    failures = 0
    for r in result.item_results:
        out = r.output
        if not isinstance(out, dict):
            failures += 1
            continue
        verdicts.append(str(out.get("verdict", "?")))
        winning_models.append(str(out.get("winning_model", "?")))

    print()
    print(f"Items: {len(result.item_results)}  failures: {failures}")
    print(f"Verdict distribution:        {dict(Counter(verdicts))}")
    print(f"Winning model distribution:  {dict(Counter(winning_models))}")

    get_client().flush()


if __name__ == "__main__":
    main()
