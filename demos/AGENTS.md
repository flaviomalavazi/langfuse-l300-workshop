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

**UI prep:** none.

**Run:** `uv run 01_scores_from_app.py`

**What lands in the UI:**
- Tracing → filter by tag `demo-1` → one new trace called `assistant-turn`.
- That trace has two scores attached: `contains_email` (BOOLEAN) and
  `user_feedback` (NUMERIC).

**Pause for the user to:** open the trace and confirm both scores appear in
the right-hand panel.

**Bridge:** *"You just attached scores to a single live trace. Demo 2 turns
that into a repeatable test suite."*

### Demo 2 — `02_dataset_and_experiment.py`

**Goal:** establish a dataset, run two prompt variants against it, get a
single side-by-side comparison.

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

**Pause for the user to:** open the dataset's Runs tab and toggle between
the two runs. The accuracy delta is the shipping decision.

**Bridge:** *"Now we move from offline experiments to scoring live traffic
with an LLM judge. First we need some traffic to score."*

### Demo 3 — `03_generate_traffic.py`

**Goal:** seed ~20 traces tagged `judge-demo` so an LLM-as-a-judge evaluator
configured in the UI has fresh targets.

**UI prep:** none for the script. **After it runs**, the user does the LLM
judge configuration in the UI:
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
- After the user finishes the UI setup above: Scores tab on each trace
  shows the judge's verdict + reasoning.

**Pause for the user to:** complete the LLM-as-a-judge setup in the UI,
then open the *judge's own trace* (Tracing → environment filter
`langfuse-llm-as-a-judge`) and read the reasoning field. The point: the
judge is debuggable, not a black box.

**Bridge:** *"The judge is one source of scores. Humans are the other. Demo
4 wires the queue that lets domain experts grade the same traces."*

### Demo 4 — `04_bulk_assign_to_queue.py`

**Goal:** show how to pipe a Langfuse filter into an annotation queue without
manual clicking.

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

**Pause for the user to:** open the queue, work one item end-to-end (score
+ comment + Complete + next), then observe the resulting Score on the
trace.

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
- **The Python SDK is pinned to v3.** Do not casually upgrade to v4 —
  several APIs the demos call (`start_as_current_span`, `update_trace`)
  are deprecated in v4 and require a thoughtful migration. See
  `VERIFICATION_NOTES.md` one folder up for the full list of v3 APIs in
  use and the migration link.
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
