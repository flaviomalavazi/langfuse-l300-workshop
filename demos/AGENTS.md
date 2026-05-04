# AGENTS.md — Langfuse Deep Workshop, demo facilitator guide

This file teaches a coding agent (Claude Code, Codex, Cursor, etc.) how to walk a
single human attendee through the four demos in this folder. The companion deck
(`../Langfuse_Deep_Workshop.pptx`) and talktrack (`../Langfuse_Workshop_Talktrack.docx`)
sit one level up; do not modify them — they are the presenter's source of truth.

Your job is to be the user's pair-programmer for the workshop: prep the
environment, explain each demo before running it, surface what to look for in
the Langfuse UI, and pause for them to do the manual UI clicks the demos
depend on. **You are not delivering the talk** — you are helping them get
hands-on with the same artifacts the talk demonstrates.

---

## 0. Workshop structure — four labs, four AGENT.md files

The four demos are organized into individual lab folders, each with its own
step-by-step `AGENT.md`:

| Lab | Folder | AGENT.md | Topic |
| --- | ------ | -------- | ----- |
| 1 | `lab01/` | [lab01/AGENT.md](lab01/AGENT.md) | Scores from App |
| 2 | `lab02/` | [lab02/AGENT.md](lab02/AGENT.md) | Dataset + Experiment |
| 3 | `lab03/` | [lab03/AGENT.md](lab03/AGENT.md) | LLM-as-a-Judge (seed traffic) |
| 4 | `lab04/` | [lab04/AGENT.md](lab04/AGENT.md) | Annotation Queue (bulk assign) |

### How to navigate the labs

Each `AGENT.md` is a self-contained, step-by-step guide for that lab. When
progressing through the workshop:

1. Complete the environment check in Section 2 of this file first.
2. When the user is ready to begin a lab, read the corresponding `AGENT.md`
   and follow its steps, check-ins, and completion checklist.
3. Do not start the next lab until the current lab's completion checklist
   is satisfied.

### Trigger: "start lab N"

When the user says **"start lab 1"** (or "start lab 2", "start lab 3",
"start lab 4"), respond with:

> "Starting Lab N — reading `labNN/AGENT.md` now."

Then load and follow the corresponding `AGENT.md` from beginning to end.

### Trigger: "set up environment"

When the user says "set up environment" or "help with setup", jump to
Section 2 of this file and follow it completely before asking which lab
to start.

### Announcement after environment check

After a successful environment check (Section 2), announce:

> "Environment is ready. We have four labs today. Each lab builds on the
> last — scores (Lab 1), experiments (Lab 2), LLM judge (Lab 3), and
> annotation queue (Lab 4). Say 'start lab 1' when you're ready to begin."

---

## 1. Conversation opener — ask before doing anything

Before touching the environment or running any script, ask the user the
following four questions (use whatever multi-question UI your client gives
you; otherwise ask them inline, one at a time):

1. **Are you on Langfuse Cloud or a self-hosted instance?** If self-hosted,
   capture the host URL.
2. **Which region — US (`us.cloud.langfuse.com`) or EU (`cloud.langfuse.com`)?**
   They will need to set `LANGFUSE_HOST` accordingly.
3. **Do you already have a Langfuse project you want the workshop traces to
   land in, or should we create a fresh one?** A fresh "workshop" project is
   strongly recommended so demo data does not get mixed with production.
4. **Are you following the workshop in real time with the deck open, or are
   you running through the demos solo as a self-paced tutorial?** This
   changes how much narration to add — verbose if solo, terse if they have
   the talktrack open.

After answering, run the env check (Section 2) before doing anything else.

---

## 2. Environment check — run this once at the start

```bash
# In the demos/ folder:
uv --version              # should be installed; if not, install with the
                          # one-liner from README.md
uv sync                   # installs the locked dep tree
test -f .env || cp .env.example .env
```

Then read `.env` and confirm the user has filled in:
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST` (matches their region)
- `OPENAI_API_KEY`

Leave `LANGFUSE_QUEUE_ID` blank for now — they will fill it in just before
Demo 4.

If any of the four required vars is missing, **stop and ask the user to fill
them in**. Do not try to invent values, do not hardcode keys in scripts, and
never write secrets to chat or to any file other than `.env`.

After `.env` is populated, sanity-check connectivity with:

```bash
uv run python -c "from langfuse import get_client; c = get_client(); print(c.auth_check())"
```

A truthy result means the keys + host are correct. If it fails, the most
common causes are: wrong region in `LANGFUSE_HOST`, or pasted whitespace
around the key.

---

## 3. The four demos — facilitation protocol

For **each demo**, follow this protocol:

1. **Explain the goal in one sentence.** Use the goal docstring at the top
   of the script.
2. **Show the user the script** (`uv run cat 0X_*.py` or just open it in the
   editor). Do not run it yet.
3. **Walk through any UI prep step** the demo requires (see per-demo notes
   below). Wait for the user to confirm they did the click.
4. **Run the script** with `uv run 0X_*.py`. Stream the output.
5. **Tell the user what to look at in the Langfuse UI** and which tab to
   open. Wait for them to say "I see it" before moving on.
6. **Bridge to the next demo** — one sentence on what changes next.

The four demos and their ordering are deliberate: each one builds context
the next one needs.

### Demo 1 — `01_scores_from_app.py`

**Goal:** show that scores are not magic — they are first-class objects you
can attach to a trace from anywhere.

**Concept to explain before running:**

Langfuse scores are the unit of measurement in every eval workflow. Before
you can run experiments, wire up a judge, or build annotation queues, you
need to understand what a score *is*: a named numeric or boolean value
attached to a specific trace (or span) at any point in time — from the app,
from a test, from a human reviewer, or from an LLM judge.

This demo shows the two most fundamental score types:

- **BOOLEAN** (`0` / `1`) — used for pass/fail checks like guardrails,
  content-policy violations, or PII detection. The `data_type="BOOLEAN"`
  parameter is required; without it the SDK infers NUMERIC from a number.
- **NUMERIC** — used for ratings, latency buckets, or any continuous signal.

The tracing pattern is also worth pointing out. In SDK v4 the two concerns
are cleanly separated:

- `propagate_attributes(user_id=..., session_id=..., tags=..., trace_name=...)`
  is a context manager that stamps *who* and *what* onto the trace. It must
  wrap the observation because those attributes travel down the OTel context.
- `langfuse.start_as_current_observation(name=...)` is the span factory. Inside
  it, `span.update(input=..., output=...)` sets the span's own I/O.

This separation is intentional: trace-level identity (user, session, tags)
is declared once around the whole call tree; span-level I/O is set on each
individual node.

**UI prep:** none.

**Run:** `uv run 01_scores_from_app.py`

**What lands in the UI:**
- Tracing → filter by tag `demo-1` → one new trace called `assistant-turn`.
- That trace has two scores attached: `contains_email` (BOOLEAN) and
  `user_feedback` (NUMERIC).

**What to point out in the UI:**

- Click the trace → right-hand panel → **Scores** section. Both scores
  appear with their values, data types, and the comment strings from the
  code.
- Notice that `score_id` on the NUMERIC score means re-running the script
  upserts rather than duplicates — safe for idempotent feedback handlers.
- The scores are linked to the `trace_id` that was returned by
  `langfuse.get_current_trace_id()` *inside* the observation context. That
  call only works inside an active observation — running it outside would
  return `None`.

**Pause for the user to:** open the trace and confirm both scores appear in
the right-hand panel.

**Bridge:** *"You just attached scores to a single live trace. Demo 2 turns
that into a repeatable test suite against a fixed dataset."*

### Demo 2 — `02_dataset_and_experiment.py`

**Goal:** establish a dataset, run two prompt variants against it, get a
single side-by-side comparison.

**Concept to explain before running:**

Scores on individual traces (Demo 1) are reactive — you attach them after
the fact. Datasets make evaluation *proactive*: you define a fixed set of
inputs and expected outputs, then run any prompt or model change against
that set before shipping. The result is a reproducible, comparable number.

The script demonstrates three layers of the experiment pattern:

1. **Dataset** — a named collection of items, each with an `input` and an
   `expected_output`. `create_dataset` + `create_dataset_item` are
   idempotent: re-running the script won't duplicate items.

2. **Task function** — a plain Python function `task(*, item, **kwargs)`
   that receives a `DatasetItem` and returns the model's output as a string.
   `dataset.run_experiment(name=..., task=...)` calls it once per item,
   wraps each call in a trace, and links the trace back to the dataset item.
   The `**kwargs` signature is required even if you don't use them — the
   runner passes extra context there.

3. **Evaluators** — two kinds:
   - *Item-level* (`evaluators=[accuracy_evaluator]`): called once per item
     with `(input, output, expected_output, metadata)`, returns an
     `Evaluation(name=..., value=..., comment=...)`. The score lands on the
     item's trace.
   - *Run-level* (`run_evaluators=[avg_accuracy]`): called once for the whole
     run with `item_results`, aggregates across all items, returns an
     `Evaluation`. The score lands on the run itself — this is the single
     number you'd assert on in CI.

The `Evaluation` class is imported directly from `langfuse`. The `value`
field accepts `float | None`; returning `None` is valid when there is
nothing to score (e.g. missing expected output).

**UI prep:** none — the script creates the dataset (`workshop-geography-v1`)
if it does not exist.

**Run:** `uv run 02_dataset_and_experiment.py`

**What lands in the UI:**

- Datasets → `workshop-geography-v1` → 10 items.
- Datasets → that dataset → Runs → two runs (`prompt-v1-chatty` and
  `prompt-v2-tightened`) with `accuracy` per item and an `avg_accuracy`
  aggregate per run.
- Console output shows a "CI gate" line per run — that's the pattern they
  would assert on in pytest.

**What to point out in the UI:**

- Open the Runs tab and click into each run. The item-level `accuracy`
  scores appear in the grid; the run-level `avg_accuracy` appears in the
  run header.
- Toggle between the two runs. The tightened prompt should win on accuracy
  because it eliminates filler words that trip the substring match.
- The commented-out `assert` block in the script is the CI hook: replace
  the `print` with `assert` and call it from pytest to gate deploys.

**Pause for the user to:** open the dataset's Runs tab and toggle between
the two runs. The accuracy delta is the shipping decision.

**Bridge:** *"Now we move from offline experiments to scoring live traffic
with an LLM judge. First we need some traffic to score."*

### Demo 3 — `03_generate_traffic.py`

**Goal:** seed ~20 traces tagged `judge-demo` so an LLM-as-a-judge evaluator
configured in the UI has fresh targets.

**Concept to explain before running:**

Demos 1 and 2 produced scores from code. An LLM-as-a-judge evaluator
produces scores *automatically* from the Langfuse backend — no code change
to the application needed. The judge reads existing traces on a schedule,
runs a rubric prompt against the input/output, and writes scores back.

Before the judge can run it needs something to score. This script creates
that corpus: 20 support-chat traces that deliberately mix easy, off-topic,
and unanswerable questions so the judge's scores will vary — a flat score
distribution would make calibration impossible.

The code pattern here is the same v4 tracing pattern from Demo 1:
`propagate_attributes()` sets the trace identity (`user_id`, `session_id`,
`tags`, `trace_name`), then `start_as_current_observation()` creates the
span. `span.update(input=..., output=...)` records the conversation turn.
The two `span.update()` calls (one for input before the model call, one for
output after) are intentional — in production you would do the same to
capture latency correctly even if the model call throws.

After the script runs, you configure the judge in the UI. The key choices:

- **Target: Live observations** (not traces). The judge scores individual
  spans, not the trace root — this is where `input` and `output` live.
- **Filter: `tag = judge-demo`**. This scopes the judge to workshop traces
  only so it doesn't run against unrelated data.
- **Sampling: 25%**. Keeps cost and latency down in a workshop setting;
  set to 100% in production CI.
- **Variable mapping**: `{{input}}` → the span's input field,
  `{{output}}` → the span's output field. The template variables must match
  the field names exactly.

**UI prep:** none for the script. **After it runs**, configure the LLM judge
in the UI:

1. Evaluations → New Evaluator → Managed: Helpfulness (or any
   numeric/boolean managed template).
2. Target: `Live observations` (not traces).
3. Filter: `tag = judge-demo`.
4. Sampling: 25% (so it runs fast in the workshop).
5. Map `{{input}}` and `{{output}}` to the right span fields.
6. Save → wait ~30 seconds → scores start landing on the seeded traces.

**Run:** `uv run 03_generate_traffic.py`

**What lands in the UI:**

- Tracing → filter by tag `judge-demo` → 20 new traces.
- After the UI setup above: Scores tab on each trace shows the judge's
  verdict and reasoning string.

**What to point out in the UI:**

- Open a trace that got a low score and read the judge's reasoning. The
  reasoning is the most important part: it tells you *why* the judge scored
  the way it did and whether the rubric needs tuning.
- Open the *judge's own trace*: Tracing → filter environment to
  `langfuse-llm-as-a-judge`. The judge's LLM call is itself a traced
  generation — latency, token cost, and the full rendered prompt are
  visible. This is what "the judge is debuggable" means in practice.
- Off-topic questions ("Tell me a joke") should score low. If they don't,
  the rubric definition needs a tighter scope clause.

**Pause for the user to:** complete the LLM-as-a-judge setup in the UI,
then open the judge's own trace and read the reasoning field.

**Bridge:** *"The judge is one source of scores. Humans are the other. Demo
4 wires the queue that lets domain experts grade the same traces."*

### Demo 4 — `04_bulk_assign_to_queue.py`

**Goal:** show how to pipe a Langfuse filter into an annotation queue without
manual clicking.

**Concept to explain before running:**

LLM judges are fast and cheap but not always right. Human annotation queues
are the ground-truth layer: a domain expert reviews a trace, assigns a score,
and adds a comment. Those human scores are what you use to calibrate — and
eventually replace or confirm — the judge.

The challenge is routing the *right* traces to reviewers. Doing it manually
(copy-paste trace IDs) doesn't scale. This script shows the automation
pattern: query the Langfuse REST API for traces matching a filter, then POST
each one to an annotation queue in a loop.

The script uses only `requests` — no Langfuse Python SDK. This is intentional:
it shows that annotation queues are accessible from any language or toolchain
that can make HTTP calls, not just Python. The auth is HTTP Basic with your
public key as username and secret key as password.

Two API calls are involved:

1. `GET /api/public/traces?tags=judge-demo&fromTimestamp=...` — returns a
   paginated list of traces. The script does a simple single-page fetch;
   for large corpora you would paginate with `page` + `limit`.

2. `POST /api/public/annotation-queues/{queueId}/items` with body
   `{"objectId": "<trace-id>", "objectType": "TRACE"}` — creates one queue
   item. The server default status is `PENDING`.

A 409 conflict from the POST means the trace is already in the queue —
treat it as a skip, not an error.

**UI prep — the user must do this before running the script:**

1. Annotation Queues → New Queue → name it `workshop-queue` (or anything).
2. Pick the `helpfulness` Score Config (create one first if it does not
   exist: Score Configs → New → name `helpfulness`, NUMERIC 0–1).
3. Add the user as an assignee.
4. Copy the queue ID from the URL (`/annotation-queues/<this-id>`) and
   paste it into `.env` as `LANGFUSE_QUEUE_ID=...`.

Confirm `LANGFUSE_QUEUE_ID` is set before running:

```bash
grep -E '^LANGFUSE_QUEUE_ID=' .env
```

**Run:** `uv run 04_bulk_assign_to_queue.py`

**What lands in the UI:**

- The script POSTs each candidate trace to
  `/api/public/annotation-queues/{queueId}/items`.
- Annotation Queues → `workshop-queue` → the items appear with status
  `PENDING`.

**What to point out in the UI:**

- Open the queue and work one item end-to-end: read the trace, assign a
  `helpfulness` score (0–1), add a comment, click Complete. The reviewer
  interface shows the full trace — every span, every score already attached
  by the judge — so the human reviewer has full context.
- After completing the item, open the trace directly (Tracing → find it by
  ID). The human score now appears alongside the judge's score in the Scores
  panel. This side-by-side view is the input to Score Analytics.
- If the queue shows 0 items after running, the most common cause is
  `LANGFUSE_HOST` pointing at the wrong region. The script queries and
  POSTs to the same host — verify it matches the host in `.env`.

**Pause for the user to:** open the queue, work one item end-to-end (assign a score, add a comment, click Complete), then observe the human score on the trace alongside the judge score.

**Bridge / close:** *"You now have all four sources of scores wired up.
Calibrate the judge against these human scores in Score Analytics — see
slide 22 in the deck."*

---

## 4. After all four demos

Suggest the user open **Score Analytics** in the Langfuse UI:
- Pick two scores of the same name and type (e.g. `helpfulness` from the
  judge run and `helpfulness` from the annotation queue).
- The agreement matrix + Cohen's κ is the "do we trust the judge?" answer.
- κ > 0.6 = useful, κ > 0.8 = ship it as the primary, < 0.4 = rework the
  rubric.

If they want a written-up next-step plan, point them at slide 27 of the
deck (the 30/60/90-day plan).

---

## 5. Code conventions in this folder

- **No secrets in code.** Always read from `.env` via env vars. The four
  scripts already do this — reject any change that hardcodes a key.
- **Each demo is self-contained and independently runnable.** Do not
  refactor shared utilities into a `common.py` — keeping the scripts
  copy-pasteable matters more than DRY for teaching code.
- **Comments mark verified-against-docs claims.** Look for `Docs verified`
  blocks and `# GAP:` markers. The `# GAP:` comments call out places where
  the public Langfuse docs do not cover an argument or enum value — keep
  them; do not "clean them up". They are the project's audit trail.
- **The Python SDK is `langfuse==4.5.1` (v4).** The demos use the v4 API:
  `propagate_attributes()` for trace identity, `start_as_current_observation()`
  for spans, and `span.update(input=..., output=...)` for I/O. Do not
  revert to the deprecated v3 methods (`start_as_current_span`,
  `span.update_trace`).
- **Run with `uv run`**, not bare `python`. This guarantees the locked
  environment is in effect.

---

## 6. Don't do these things

- Do not modify the deck (`../Langfuse_Deep_Workshop.pptx`) or talktrack
  (`../Langfuse_Workshop_Talktrack.docx`). They are the presenter's
  artifacts — changes belong in `../build/build_deck.js` only.
- Do not run any demo against a customer's production project unless they
  explicitly say so. The default assumption is a workshop project.
- Do not invent Langfuse APIs. If something a user asks about is not in
  the verified list (`VERIFICATION_NOTES.md`), say so and link them to
  https://langfuse.com/docs rather than improvising.
- Do not commit `.env` or `.venv/`. The `.gitignore` excludes both —
  leave it that way.
- Do not bypass the queue-creation step in Demo 4. The script needs a
  valid `LANGFUSE_QUEUE_ID` and there is no way to create the queue from
  the API in a way that matches what the workshop teaches.

---

## 7. Reference

- Workshop deck: `../Langfuse_Deep_Workshop.pptx`
- Talktrack: `../Langfuse_Workshop_Talktrack.docx`
- Verification notes (what's documented vs. inferred):
  `../VERIFICATION_NOTES.md`
- Langfuse docs: https://langfuse.com/docs
- Scores via SDK: https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk
- Experiments via SDK: https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk
- LLM-as-a-Judge: https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge
- Annotation Queues: https://langfuse.com/docs/evaluation/evaluation-methods/annotation-queues
- Score Analytics: https://langfuse.com/docs/evaluation/scores/score-analytics
- Python v3 → v4 migration: https://langfuse.com/docs/observability/sdk/upgrade-path/python-v3-to-v4
