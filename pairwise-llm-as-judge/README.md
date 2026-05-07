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
- `SYSTEM_A_MODEL`, `SYSTEM_B_MODEL`, `JUDGE_MODEL` (any chat-completions model)

## Run

```bash
uv run python run_pipeline.py
```

This is idempotent on the dataset (`seed_dataset.py` only writes items if the dataset is empty) but creates a new timestamped run pair every invocation.

## Layout

| File | Purpose |
| --- | --- |
| [src/pairwise_judge/seed_dataset.py](src/pairwise_judge/seed_dataset.py) | Create the demo dataset and items via `langfuse.create_dataset(_item)` |
| [src/pairwise_judge/candidates.py](src/pairwise_judge/candidates.py) | Two `@observe`-decorated task functions (System A, System B) |
| [src/pairwise_judge/judge.py](src/pairwise_judge/judge.py) | Two-pass pairwise judge with structured-JSON verdicts and swap mitigation |
| [src/pairwise_judge/experiments.py](src/pairwise_judge/experiments.py) | `dataset.run_experiment(...)` orchestration + score-writing |
| [src/pairwise_judge/aggregate.py](src/pairwise_judge/aggregate.py) | Win/tie/loss summary, win-rate-with-ties, run-level scoring |
| [run_pipeline.py](run_pipeline.py) | Entry point that wires the four phases together |

## Methodology notes

- **Why two passes per pair?** The paper explicitly calls out position bias: a judge can prefer whichever response appears first regardless of quality. Running the comparison twice with sides swapped and resolving disagreement as a tie (PandaLM convention) cuts position bias substantially.
- **Why win-rate with ties = 0.5?** With a single A-vs-B comparison per item, `(wins + 0.5·ties) / n` is the maximum-likelihood Bradley-Terry estimate of P(A beats B). For multi-system tournaments you'd want a real Bradley-Terry / Elo fit; this codebase only handles the two-system case.
- **Why force JSON output?** The paper recommends structured outputs (e.g. `\boxed{XX}`) for deterministic parsing. We use OpenAI's `response_format={"type":"json_object"}` and a strict schema.

## Extending this

- **More systems:** loop `run_candidate_experiment` over a list and run the judge over every pair, then plug into a Bradley-Terry MLE.
- **Custom judge:** replace `_JUDGE_SYSTEM_PROMPT` in [judge.py](src/pairwise_judge/judge.py); per the paper, decomposing criteria into named dimensions and adding 2–3 few-shot examples reliably improves judge agreement.
- **Real datasets:** replace `seed_dataset.py` with a loader that reads from your evaluation set and calls `langfuse.create_dataset_item(...)` once per row.
