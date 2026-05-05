# Langfuse Deep Workshop — Demos

Four runnable demos paired with the deck. Each one is self-contained: it can
be run independently and produces visible artifacts in the Langfuse UI.

## Setup (once) — uv

The project is managed with [uv](https://docs.astral.sh/uv). The `pyproject.toml`
and `uv.lock` in this folder pin the exact dependency tree everyone in the
workshop should be running against.

```bash
# Install uv (skip if you already have it):
curl -LsSf https://astral.sh/uv/install.sh | sh

# From inside this folder:
uv sync           # creates .venv/ and installs the locked deps
cp .env.example .env
$EDITOR .env      # paste your Langfuse + OpenAI keys
```

`uv sync` reads `uv.lock` exactly — you'll get the same `langfuse 4.5.1`,
`openai`, and `requests` versions everyone else in the workshop has.

### Working with a coding agent

Have Claude Code, Codex, or Cursor open in this folder? An [`AGENTS.md`](./AGENTS.md)
file lives next to this README. Tell your agent *"follow AGENTS.md"* and it
will walk you through the workshop demo by demo, checking your env, watching
the Langfuse UI for the right artifacts, and pausing for you to do each
manual UI click.

## The four demos

| # | File | Deck slide | What it shows |
|---|------|------------|---------------|
| 1 | `01_scores_from_app.py` | DEMO 1 (slide 9) | Emit `BOOLEAN` guardrail and `NUMERIC` user-feedback scores from an instrumented trace using `langfuse.create_score()`. |
| 2 | `02_dataset_and_experiment.py` | DEMO 2 (slide 14) | Create a dataset, run two experiments (prompt v1 vs v2) with `dataset.run_experiment()`, item-level evaluator + run-level aggregator. |
| 3 | `03_generate_traffic.py` | DEMO 3 (slide 20) prep | Seed ~20 tagged traces so an LLM-as-a-judge evaluator has something to run on. |
| 4 | `04_bulk_assign_to_queue.py` | DEMO 4 (slide 24) | Bulk-attach traces from a Langfuse filter to an annotation queue via the public REST API (`POST /api/public/annotation-queues/{queueId}/items`). |

## Run order (for the live workshop)

Use `uv run` so each script picks up the locked environment automatically:

```bash
uv run 01_scores_from_app.py
uv run 02_dataset_and_experiment.py
uv run 03_generate_traffic.py        # run ~30s before the judge demo
# configure the LLM-as-a-judge template in the Langfuse UI and point it at the "workshop" tag
uv run 04_bulk_assign_to_queue.py    # needs LANGFUSE_QUEUE_ID from the UI
```

(If you've already activated the venv with `source .venv/bin/activate`, the
plain `python <script>.py` form works too.)

## Docs references (verified 2026-05)

- `langfuse.create_score()` — https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk
- `dataset.run_experiment()` — https://langfuse.com/docs/evaluation/experiments/datasets (and /experiments-via-sdk)
- Annotation queue API — https://api.reference.langfuse.com (operation `annotationQueues_createQueueItem`)

## Notes / gaps called out in the demos

Every script has a `# GAP:` comment wherever an argument or enum value could NOT
be verified in public Langfuse docs. Those comments are intentional — per the
workshop brief, nothing has been invented to fill a documentation gap.
