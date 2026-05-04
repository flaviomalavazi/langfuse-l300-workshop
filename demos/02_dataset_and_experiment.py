"""
DEMO 2 — Dataset + experiment: comparing prompt v1 against prompt v2.

Goal
----
A minimum-viable, repeatable offline eval:
  1. Create (or reuse) a dataset of ~10 Q&A pairs.
  2. Run the same dataset through two different system prompts.
  3. Attach an item-level evaluator (`accuracy`) and a run-level evaluator
     (`avg_accuracy`) so each experiment run gets a single summary number
     AND every item gets its own score.
  4. Show the two runs side-by-side in the Langfuse "Experiments" tab.

This is the "reproducible CI for prompts" pattern. Wire this into your CI
on every prompt / model change.

Docs verified 2026-04:
  https://langfuse.com/docs/evaluation/experiments/datasets
  https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk

Run:
    python 02_dataset_and_experiment.py
"""

import os

from langfuse import Evaluation, get_client
from langfuse.openai import openai

langfuse = get_client()
client = openai.OpenAI()

DATASET_NAME = "workshop-geography-v1"

# ---------------------------------------------------------------------------
# 1. Seed the dataset (idempotent-ish: create_dataset + create_dataset_item
#    will upsert by name / id).
# ---------------------------------------------------------------------------
SEED_ITEMS = [
    {"input": "What is the capital of France?",   "expected_output": "Paris"},
    {"input": "What is the capital of Germany?",  "expected_output": "Berlin"},
    {"input": "What is the capital of Japan?",    "expected_output": "Tokyo"},
    {"input": "What is the capital of Brazil?",   "expected_output": "Brasilia"},
    {"input": "What is the capital of Canada?",   "expected_output": "Ottawa"},
    {"input": "What is the capital of Egypt?",    "expected_output": "Cairo"},
    {"input": "What is the capital of Kenya?",    "expected_output": "Nairobi"},
    {"input": "What is the capital of Australia?","expected_output": "Canberra"},
    {"input": "What is the capital of Thailand?", "expected_output": "Bangkok"},
    {"input": "What is the capital of Portugal?", "expected_output": "Lisbon"},
]


def ensure_dataset() -> None:
    langfuse.create_dataset(
        name=DATASET_NAME,
        description="Workshop demo — capital cities Q&A.",
        metadata={"source": "workshop", "version": 1},
    )
    for item in SEED_ITEMS:
        langfuse.create_dataset_item(
            dataset_name=DATASET_NAME,
            input={"question": item["input"]},
            expected_output=item["expected_output"],
        )


# ---------------------------------------------------------------------------
# 2. Two tasks — same dataset, different prompts.
# ---------------------------------------------------------------------------
def _call_model(system_prompt: str, question: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def task_prompt_v1(*, item, **kwargs):
    """Baseline prompt — chatty."""
    # `item` is a DatasetItem because we run via `dataset.run_experiment()`.
    # For Langfuse datasets, access input as `item.input` (attribute).
    question = item.input["question"]
    return _call_model(
        "You are a helpful assistant. Answer any geography question.",
        question,
    )


def task_prompt_v2(*, item, **kwargs):
    """Tightened prompt — asks for a single-word answer."""
    question = item.input["question"]
    return _call_model(
        "You are a geography expert. Answer with ONLY the city name, no "
        "other words, no punctuation.",
        question,
    )


# ---------------------------------------------------------------------------
# 3. Evaluators.
#    Item-level: `accuracy` — substring match against expected_output.
#    Run-level:  `avg_accuracy` — mean over all items in the run.
# ---------------------------------------------------------------------------
def accuracy_evaluator(*, input, output, expected_output, metadata, **kwargs):
    """Case-insensitive substring match. expected_output is a string here."""
    if expected_output and expected_output.lower() in (output or "").lower():
        return Evaluation(name="accuracy", value=1.0, comment="correct")
    return Evaluation(
        name="accuracy", value=0.0,
        comment=f"expected {expected_output!r}, got {output!r}",
    )


def avg_accuracy(*, item_results, **kwargs):
    values = [
        e.value
        for r in item_results
        for e in r.evaluations
        if e.name == "accuracy"
    ]
    if not values:
        return Evaluation(name="avg_accuracy", value=None)
    mean = sum(values) / len(values)
    return Evaluation(
        name="avg_accuracy",
        value=mean,
        comment=f"{mean:.1%} correct across {len(values)} items",
    )


# ---------------------------------------------------------------------------
# 4. Run both experiments against the same dataset.
# ---------------------------------------------------------------------------
def main() -> None:
    ensure_dataset()
    dataset = langfuse.get_dataset(DATASET_NAME)

    for run_name, task in [
        ("prompt-v1-chatty",   task_prompt_v1),
        ("prompt-v2-tightened", task_prompt_v2),
    ]:
        result = dataset.run_experiment(
            name=run_name,
            description="Workshop A/B — prompt variant comparison.",
            task=task,
            evaluators=[accuracy_evaluator],
            run_evaluators=[avg_accuracy],
            max_concurrency=5,
        )
        print(f"\n=== {run_name} ===")
        print(result.format())

        # ---- CI shipping gate (illustrative — wire this into pytest) ----
        # The run-level evaluator above attached `avg_accuracy` to this run.
        # In CI you would assert on it directly:
        #
        #     assert any(
        #         e.name == "avg_accuracy" and e.value >= 0.85
        #         for e in result.run_evaluations
        #     ), f"{run_name}: avg_accuracy regressed below 0.85"
        #
        # The demo prints instead of asserting so the workshop can keep going.
        for e in result.run_evaluations:
            if e.name == "avg_accuracy":
                gate = "PASS" if (e.value or 0) >= 0.85 else "FAIL"
                print(f"  CI gate (avg_accuracy ≥ 0.85): {gate}  ({e.value:.2f})")

    langfuse.flush()
    print("\nOpen Datasets → workshop-geography-v1 → Runs to compare.\n")


if __name__ == "__main__":
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "OPENAI_API_KEY"):
        if not os.environ.get(k):
            raise SystemExit(f"Missing env var: {k}. See demos/README.md.")
    main()
