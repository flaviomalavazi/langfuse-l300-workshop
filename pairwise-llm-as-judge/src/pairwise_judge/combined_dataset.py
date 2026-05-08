"""Build a combined Langfuse dataset for UI-driven pairwise evaluation.

Given the outputs of two candidate runs (System A, System B) over a shared
source dataset, this module creates a NEW Langfuse dataset whose items each
hold the original question alongside both responses. With that combined
dataset in place, a user can configure a single LLM-as-a-Judge evaluator in
the Langfuse UI and run pairwise comparisons interactively — no code path
needed.

Item input layout (model metadata first so the judge can tag its verdict):

    {
      "model_a": "<system A model id>",
      "model_b": "<system B model id>",
      "question": "<original question>",
      "response_a": "<System A response>",
      "response_b": "<System B response>"
    }
"""

from __future__ import annotations

import time

from langfuse import get_client

from .config import Config
from .experiments import CandidateRun


def build_combined_dataset(
    cfg: Config,
    run_a: CandidateRun,
    run_b: CandidateRun,
    target_dataset_name: str | None = None,
) -> str:
    """Create a combined dataset that pairs each item's A and B responses.

    Returns the dataset name. The dataset is created idempotently on `name`
    (Langfuse dedupes by name); items are only inserted if the dataset is
    currently empty, mirroring the ``seed_dataset`` pattern.
    """
    langfuse = get_client()
    source = langfuse.get_dataset(cfg.dataset_name)

    name = target_dataset_name or f"{cfg.dataset_name}-combined"
    langfuse.create_dataset(
        name=name,
        description=(
            f"Pairwise side-by-side dataset built from runs "
            f"'{run_a.run_name}' (A) and '{run_b.run_name}' (B). "
            "Use a single LLM-as-a-Judge evaluator in the UI."
        ),
        metadata={
            "purpose": "pairwise-judge-ui",
            "source_dataset": cfg.dataset_name,
            "run_a": run_a.run_name,
            "run_b": run_b.run_name,
            "model_a": cfg.system_a_model,
            "model_b": cfg.system_b_model,
            "system_a_name": cfg.system_a_name,
            "system_b_name": cfg.system_b_name,
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )

    existing = langfuse.get_dataset(name)
    if len(existing.items) > 0:
        print(
            f"Combined dataset '{name}' already has {len(existing.items)} items; "
            "skipping insert. Delete the dataset (or use a different "
            "target_dataset_name) to rebuild."
        )
        return name

    a_by_item = run_a.by_item()
    b_by_item = run_b.by_item()

    inserted = 0
    skipped = 0
    for item in source.items:
        a = a_by_item.get(item.id)
        b = b_by_item.get(item.id)
        if a is None or b is None:
            skipped += 1
            continue

        question = (
            item.input.get("question")
            if isinstance(item.input, dict)
            else str(item.input)
        )

        # Insertion order matters: model_a / model_b are placed first so the
        # metadata appears at the top of the input panel in the Langfuse UI
        # and the judge sees it before the question and responses.
        combined_input = {
            "model_a": cfg.system_a_model,
            "model_b": cfg.system_b_model,
            "question": question,
            "response_a": a.output,
            "response_b": b.output,
        }

        langfuse.create_dataset_item(
            dataset_name=name,
            input=combined_input,
            metadata={
                "source_dataset_item_id": item.id,
                "source_run_a": run_a.run_name,
                "source_run_b": run_b.run_name,
                "trace_id_a": a.trace_id,
                "trace_id_b": b.trace_id,
                "system_a_name": cfg.system_a_name,
                "system_b_name": cfg.system_b_name,
            },
        )
        inserted += 1

    langfuse.flush()
    print(
        f"Combined dataset '{name}': inserted {inserted} items"
        + (f" (skipped {skipped} with missing A/B output)" if skipped else "")
        + "."
    )
    return name
