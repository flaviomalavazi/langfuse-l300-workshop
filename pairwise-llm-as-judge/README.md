# Pairwise LLM-as-a-Judge on Langfuse

A Python implementation of pairwise LLM-as-a-judge evaluation, orchestrated through the Langfuse Python SDK.

Reference: [A Survey on LLM-as-a-Judge (arxiv:2411.15594)](https://arxiv.org/html/2411.15594v1).

## What this does

Given a dataset of prompts and two candidate "systems" (different model + system-prompt combos), it:

1. Runs each system over the dataset as a separate Langfuse experiment, producing one trace per item per system.
2. For each item, asks a judge LLM which response is better — twice, with sides swapped, to neutralize position bias (Wang et al. mitigation; PandaLM-style tie-on-conflict).
3. Records each verdict as a categorical `pairwise_outcome` score (`win` / `loss` / `tie`) on both candidates' traces, and writes run-level `run_win_rate` and `judge_position_conflict_rate` scores.

Everything is visible in the Langfuse UI: filter by run name to see the per-item verdicts, scroll to scores for the aggregate.

## Setup

```bash
cp .env.example .env   # then fill in keys
uv sync                # or: pip install -e .
```

Required env vars (see [.env.example](./.env.example)):
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY` (only required for the UI / SDK-driven pairwise comparison flow below)
- `SYSTEM_A_MODEL`, `SYSTEM_B_MODEL`, `JUDGE_MODEL` (any chat-completions model)

## Run

```bash
uv run python run_pipeline.py
```

This is idempotent on the dataset (`seed_dataset.py` only writes items if the dataset is empty) but creates a new timestamped run pair every invocation.

## UI-driven pairwise comparison

Instead of running the code-driven judge in [judge.py](src/pairwise_judge/judge.py), you can hand the comparison off to a Langfuse evaluator and trigger it from the UI (or from the SDK using the same prompt + schema). The flow is:

```text
seed dataset  →  run System A  →  run System B  →  build combined dataset  →  judge each item with a single LLM-as-a-Judge evaluator
```

The combined dataset's input layout for each item is:

```json
{
  "model_a": "<system A model id>",
  "model_b": "<system B model id>",
  "question": "<original question>",
  "response_a": "<System A response>",
  "response_b": "<System B response>"
}
```

`model_a` / `model_b` are placed first so the metadata appears at the top of the input panel in the Langfuse UI and the judge can tag its verdict with the producing model's name.

### Step 1 — build the combined dataset

```bash
uv run python build_combined_dataset.py
```

This re-runs both candidate systems on the source dataset, then writes a new dataset (default `<DATASET_NAME>-combined`) where each item carries both responses plus model metadata. Idempotent on dataset name; if the combined dataset already has items, it skips inserts.

### Step 2 — judge each item

Pick one of the two paths below. Both write categorical scores to each trace, so results show up side-by-side under **Datasets → `<name>-combined` → Runs → Compare**.

**Path A — SDK (recommended for repeatable runs):**

```bash
uv run python run_pairwise_evaluator.py
```

This:

1. Creates / versions a chat prompt named `pairwise-evaluator` in Langfuse Prompt Management. The structured-output JSON schema is stored in the prompt's `config` under the key `pairwise-evaluator-output-schema` (the Langfuse public REST API does not yet expose Playground schemas as standalone entities — see [discussion #9131](https://github.com/orgs/langfuse/discussions/9131) — so the schema is versioned alongside the prompt).
2. Triggers a single dataset run on the combined dataset using `claude-haiku-4-5-20251001` with Anthropic tool-use enforcing the schema, producing per-item `pairwise_outcome_ui` (`A` / `B` / `tie`) and `pairwise_winning_model` (real model id) scores.

**Path B — Langfuse UI:**

1. **Datasets** → open `<name>-combined` to inspect items.
2. **Evaluators** → New evaluator → LLM-as-a-Judge.
3. Paste the prompt from [evaluator_prompt.md](evaluator_prompt.md) and map variables:

   | Variable     | JSON path           |
   |--------------|---------------------|
   | `model_a`    | `input.model_a`     |
   | `model_b`    | `input.model_b`     |
   | `question`   | `input.question`    |
   | `response_a` | `input.response_a`  |
   | `response_b` | `input.response_b`  |

4. Attach the evaluator to the combined dataset and run.

To mitigate position bias in path B (path A runs only once per item), build a second combined dataset with `response_a` / `response_b` (and `model_a` / `model_b`) swapped, run the same evaluator, and resolve cross-pass disagreements as ties.

## Layout

| File | Purpose |
| --- | --- |
| [src/pairwise_judge/seed_dataset.py](src/pairwise_judge/seed_dataset.py) | Create the demo dataset and items via `langfuse.create_dataset(_item)` |
| [src/pairwise_judge/candidates.py](src/pairwise_judge/candidates.py) | Two task functions (System A, System B) wrapped in `start_as_current_observation` |
| [src/pairwise_judge/judge.py](src/pairwise_judge/judge.py) | Two-pass pairwise judge with structured-JSON verdicts and swap mitigation |
| [src/pairwise_judge/experiments.py](src/pairwise_judge/experiments.py) | `dataset.run_experiment(...)` orchestration + score-writing |
| [src/pairwise_judge/aggregate.py](src/pairwise_judge/aggregate.py) | Win/tie/loss summary, win-rate-with-ties, run-level scoring |
| [src/pairwise_judge/combined_dataset.py](src/pairwise_judge/combined_dataset.py) | Build the side-by-side dataset that pairs each item's A and B responses |
| [src/pairwise_judge/ui_evaluator.py](src/pairwise_judge/ui_evaluator.py) | SDK equivalent of the UI 'Run Experiment' wizard: prompt + schema + Anthropic tool-use run |
| [run_pipeline.py](run_pipeline.py) | Entry point for the code-driven judge pipeline |
| [build_combined_dataset.py](build_combined_dataset.py) | Entry point that produces the combined dataset for UI / SDK pairwise comparison |
| [run_pairwise_evaluator.py](run_pairwise_evaluator.py) | Entry point that creates the judge prompt and triggers one SDK-driven run |
| [evaluator_prompt.md](evaluator_prompt.md) | Copy-pasteable prompt + variable mapping for setting up the evaluator manually in the UI |

## Methodology notes

- **Why two passes per pair?** The paper explicitly calls out position bias: a judge can prefer whichever response appears first regardless of quality. Running the comparison twice with sides swapped and resolving disagreement as a tie (PandaLM convention) cuts position bias substantially.
- **Why win-rate with ties = 0.5?** With a single A-vs-B comparison per item, `(wins + 0.5·ties) / n` is the maximum-likelihood Bradley-Terry estimate of P(A beats B). For multi-system tournaments you'd want a real Bradley-Terry / Elo fit; this codebase only handles the two-system case.
- **Why force JSON output?** The paper recommends structured outputs (e.g. `\boxed{XX}`) for deterministic parsing. We use OpenAI's `response_format={"type":"json_object"}` and a strict schema.

## Extending this

- **More systems:** loop `run_candidate_experiment` over a list and run the judge over every pair, then plug into a Bradley-Terry MLE.
- **Custom judge:** replace `_JUDGE_SYSTEM_PROMPT` in [judge.py](src/pairwise_judge/judge.py); per the paper, decomposing criteria into named dimensions and adding 2–3 few-shot examples reliably improves judge agreement.
- **Real datasets:** replace `seed_dataset.py` with a loader that reads from your evaluation set and calls `langfuse.create_dataset_item(...)` once per row.
