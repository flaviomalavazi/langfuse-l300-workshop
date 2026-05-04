# Lab 2: Dataset + Experiment — Agent Instructions

> **For the attendee**: Paste this file's contents into your AI assistant, or say "start lab 2" if your assistant has already loaded `AGENTS.md`.

---

## Before we start

Tell the attendee:

> "Lab 1 showed scores on individual live traces — reactive measurement. Lab 2 makes evaluation **proactive**: you define a fixed dataset and run any prompt change against it before shipping. The output is a reproducible, comparable number.
>
> Make sure your terminal is open in the `demos/` directory."

---

## Your task

You are teaching Lab 2 as a live instructor. Explain the three-layer experiment pattern, walk through the script, run it, then guide the attendee to compare the two experiment runs side-by-side in the Langfuse UI.

The goal: establish a dataset, run two prompt variants against it, and get a single side-by-side comparison — the "reproducible CI for prompts" pattern.

---

## Step 1 — Understand the three-layer experiment pattern

**Announce**:

> "There are three distinct concepts here. Let me explain them before we touch any code."

**Explain**:

**Layer 1 — Dataset**: A named collection of items, each with an `input` and an `expected_output`. Think of it as a golden set of test cases you curate once and reuse forever. `create_dataset` + `create_dataset_item` are idempotent: re-running the script won't create duplicate items.

**Layer 2 — Task function**: A plain Python function `task(*, item, **kwargs)` that receives a `DatasetItem` and returns the model's output as a string. `dataset.run_experiment(name=..., task=...)` calls it once per item, wraps each call in a trace, and links the trace back to the dataset item. The `**kwargs` signature is required even if unused — the runner passes extra context there.

**Layer 3 — Evaluators**:
- *Item-level* (`evaluators=[fn]`): called once per item with `(input, output, expected_output, metadata)`, returns an `Evaluation(name=..., value=..., comment=...)`. The score lands on the item's trace.
- *Run-level* (`run_evaluators=[fn]`): called once for the whole run with `item_results`, aggregates across all items, returns an `Evaluation`. The score lands on the run itself — **this is the single number you assert on in CI**.

**Explain**: The `Evaluation` class is imported directly from `langfuse`. `value` accepts `float | None`; returning `None` is valid when there's nothing to score.

**✋ Check in**: "Does the item-level vs run-level evaluator split make sense? Any questions before we look at the code?"

---

## Step 2 — Walk through the script

**Announce**: "Let's open the script."

**Show the script** — open [lab02/02_dataset_and_experiment.py](02_dataset_and_experiment.py) or run:

```bash
cat lab02/02_dataset_and_experiment.py
```

**Point out**:

1. `ensure_dataset()` — calls `create_dataset()` + `create_dataset_item()` in a loop. These are idempotent: safe to run multiple times.
2. `task_prompt_v1` vs `task_prompt_v2` — same dataset, different system prompts. The chatty v1 includes extra words; the tightened v2 asks for a single city name. This will affect substring-match accuracy.
3. `accuracy_evaluator` — returns `Evaluation(name="accuracy", value=1.0/0.0)`. Note: it receives `expected_output` as a plain string (the value you passed to `create_dataset_item`).
4. `avg_accuracy` (run-level) — iterates `item_results`, filters by `e.name == "accuracy"`, computes the mean. Returns `Evaluation(name="avg_accuracy", value=mean)`.
5. `dataset.run_experiment(...)` takes both `evaluators=` and `run_evaluators=` — they run automatically after all task calls complete.
6. The commented-out `assert` block at the bottom — this is the CI gate pattern. Uncomment + replace the `print` with `assert` to fail a pytest run if `avg_accuracy` drops below 0.85.

**✋ Check in**: "Any questions about the evaluator signatures or how the scores get attached?"

---

## Step 3 — Run the script

**Terminal prompt**: "In `demos/`, run:"

```bash
uv run lab02/02_dataset_and_experiment.py
```

**Expected output** (abbreviated):

```
=== prompt-v1-chatty ===
<experiment run summary table>
  CI gate (avg_accuracy ≥ 0.85): PASS/FAIL  (0.XX)

=== prompt-v2-tightened ===
<experiment run summary table>
  CI gate (avg_accuracy ≥ 0.85): PASS/FAIL  (0.XX)

Open Datasets → workshop-geography-v1 → Runs to compare.
```

> The v2 (tightened) prompt should score higher than v1 (chatty) because it eliminates filler words that trip the substring match. If both pass, that's fine — the point is seeing the delta.

**If the script fails**:
- `Missing env var` → check `.env`.
- `DatasetNotFound` on the second run → first `ensure_dataset()` call failed silently; check the Langfuse connectivity output from setup.
- Rate limit errors → `max_concurrency=5` is already set; reduce to `max_concurrency=2` if the OpenAI tier is low.

**✋ Check in**: "Did both runs complete? What were the `avg_accuracy` scores?"

---

## Step 4 — Verify the dataset

**Announce**: "Let's confirm the dataset landed correctly first."

**Langfuse check**:

1. Go to **Datasets** in the Langfuse UI.
2. Open `workshop-geography-v1`.
3. You should see 10 items — capital-cities Q&A pairs.

**What to point out**:

- Each item shows its `input` (the question), `expected_output` (city name), and any metadata.
- The dataset is reusable: you can run future experiments against the same dataset without re-seeding.

**✋ Check in**: "Do you see 10 items in `workshop-geography-v1`?"

---

## Step 5 — Compare the two experiment runs

**Announce**: "Now the interesting part — the side-by-side comparison."

**Langfuse check**:

1. Still in **Datasets** → `workshop-geography-v1` → click the **Runs** tab.
2. You should see two runs: `prompt-v1-chatty` and `prompt-v2-tightened`.
3. Click into each run and look at the item-level `accuracy` scores in the grid.
4. Look at the run header — the `avg_accuracy` aggregate score is there.

**What to point out**:

- Toggle between the two runs. The tightened prompt should have fewer `0.0` accuracy items because it's less likely to include prefix words like "The capital of France is…" that break the substring match.
- The run-level `avg_accuracy` in the header is the **shipping decision number** — this is what the CI `assert` gates on.
- Click into one item's trace. You'll see the full conversation (input, model output, expected output) and the item-level `accuracy` score — the same structure as Lab 1's scores, just attached automatically by the evaluator.

**✋ Check in**: "Can you see both runs in the Runs tab? Which prompt variant won on `avg_accuracy`?"

---

## Step 6 — Connect this to CI

**Announce**: "One more concept: how this becomes a CI gate."

**Explain**: The commented-out `assert` block in the script is not decoration — it's the real pattern:

```python
assert any(
    e.name == "avg_accuracy" and e.value >= 0.85
    for e in result.run_evaluations
), f"{run_name}: avg_accuracy regressed below 0.85"
```

Drop this into a `pytest` function and call it from your deploy pipeline. Every time someone changes the system prompt or swaps the model, this test re-runs the full dataset and blocks the deploy if accuracy regresses. The dataset is your safety net; the experiment run is your proof.

**✋ Check in**: "Does this CI gate pattern fit into how you currently run tests?"

---

## Completion check

- [ ] Script ran both experiment runs to completion
- [ ] `workshop-geography-v1` dataset appears with 10 items in the UI
- [ ] Both runs appear in the Runs tab with per-item `accuracy` scores
- [ ] `avg_accuracy` aggregate is visible in each run header
- [ ] You understand how to convert the `print` to an `assert` for CI

"Excellent — you have a reproducible offline eval pipeline. Lab 3 moves from offline experiments to scoring **live traffic** using an LLM-as-a-judge evaluator. First we need some traffic to score — that's what Lab 3 generates. Ready?"
