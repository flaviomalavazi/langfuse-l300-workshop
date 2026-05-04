# Lab 1: Scores from App — Agent Instructions

> **For the attendee**: Paste this file's contents into your AI assistant, or say "start lab 1" if your assistant has already loaded `AGENTS.md`.

---

## Before we start

Tell the attendee:

> "Please make sure you have a terminal window open in the `demos/` directory and that `.env` is populated (run `grep -c '=.' .env` — you should see at least 4 non-empty lines).
>
> Lab 1 is about Langfuse **scores** — the fundamental unit of measurement for every eval workflow. Nothing else in the workshop makes sense without this."

---

## Your task

You are teaching Lab 1 as a live instructor. Explain the concept first, walk through the script, run it, then guide the attendee to verify in the Langfuse UI before moving on.

The goal: show that scores are first-class objects you can attach to any trace from application code — no eval pipeline required.

---

## Step 1 — What is a Langfuse score?

**Announce**:

> "Before running anything, let's get the mental model right."

**Explain**: A Langfuse score is a named value — numeric or boolean — attached to a specific trace or span at any point in time. It can come from anywhere: the app (guardrails, business logic), a test suite, a human reviewer, or an LLM judge. The key insight is that **scores are not locked inside an eval pipeline**. You can emit them inline, from a webhook, or from a CLI script.

This demo shows the two most fundamental score types:

- **BOOLEAN** (`0` / `1`) — pass/fail checks: guardrails, content-policy violations, PII detection. The `data_type="BOOLEAN"` parameter is **required**; without it the SDK infers NUMERIC from a number.
- **NUMERIC** — continuous signals: star ratings, latency buckets, confidence scores.

**Also explain the v4 tracing pattern** — two distinct concerns kept separate:

- `propagate_attributes(user_id=..., session_id=..., tags=..., trace_name=...)` stamps *who* and *what* onto the trace. It must wrap the observation because those attributes travel down the OTel context.
- `langfuse.start_as_current_observation(name=...)` is the span factory. Inside it, `span.update(input=..., output=...)` sets that span's own I/O.

**✋ Check in**: "Does the BOOLEAN vs NUMERIC distinction make sense? Questions before we look at the code?"

---

## Step 2 — Walk through the script

**Announce**: "Let's open the script and read it before running."

**Show the script** — open [lab01/01_scores_from_app.py](01_scores_from_app.py) in the editor or run:

```bash
cat lab01/01_scores_from_app.py
```

**Point out**:

1. `propagate_attributes()` is the outer context manager; `start_as_current_observation()` is the inner span — trace identity wraps span I/O.
2. The guardrail is a simple regex scan (`EMAIL_RE.search(answer)`) — in production this would be a real guardrail library, but the score emission pattern is identical.
3. `langfuse.create_score(..., data_type="BOOLEAN", value=0/1)` — the `data_type` parameter is what makes this a BOOLEAN, not the numeric value.
4. The `user_feedback` score passes `score_id=f"user-feedback-{uuid.uuid4()}"` — this makes the score **idempotent**: re-running upserts instead of creating a duplicate. In production, pass a deterministic ID derived from the trace and feedback event.
5. `langfuse.flush()` at the end — scores are buffered and sent async; `flush()` forces them out immediately so the audience sees results without waiting.

**✋ Check in**: "Any questions about the structure before we run?"

---

## Step 3 — Run the script

**Terminal prompt**: "In your terminal inside `demos/`, run:"

```bash
uv run lab01/01_scores_from_app.py
```

**Expected output**:

```
Trace: <some-trace-id>
Answer: <model response about the SLA>

[guardrail] contains_email = True
[feedback] user_feedback = 4/5

Flushed. Open the trace in Langfuse UI to see both scores.
```

> If `contains_email` shows `False`, the model paraphrased the email address rather than echoing it — that's fine, the guardrail still ran correctly.

**If the script fails**:
- `Missing env var` → check `.env` has `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `OPENAI_API_KEY`.
- `AuthError` → wrong region in `LANGFUSE_HOST`; re-run the auth check from the setup section.
- `ModuleNotFoundError` → run `uv sync` first.
- Running from wrong directory → must be in `demos/`, not `demos/lab01/`.

**✋ Check in**: "Did it run? What did the `contains_email` guardrail print?"

---

## Step 4 — Verify the BOOLEAN guardrail score

**Announce**: "Now let's see what landed in Langfuse."

**Langfuse check**:

1. Go to **Tracing** in the Langfuse UI.
2. Filter by tag `demo-1` — one new trace called `assistant-turn` should appear.
3. Click the trace → right-hand panel → **Scores** section.

**What to point out**:

- `contains_email` shows as BOOLEAN (0 or 1) with comment "Auto-guardrail: regex scan of the final answer."
- Notice the `data_type` column — BOOLEAN is a distinct type from NUMERIC even when the value is 0 or 1. This distinction matters in Score Analytics when you filter by type.
- The score is linked to the trace by `trace_id`, which `langfuse.get_current_trace_id()` returned **inside** the observation context. That call returns `None` if you call it outside an active span — something to watch for in production.

**✋ Check in**: "Do you see the `contains_email` score? What value is it?"

---

## Step 5 — Verify the NUMERIC user feedback score

**Announce**: "Same trace — look at the second score."

**Langfuse check**: Still in the **Scores** section of the same trace:

**What to point out**:

- `user_feedback` shows as NUMERIC, value `4`, comment "User rated this 4/5 stars."
- The `score_id` field is present — click the score detail if your UI shows it. This is the idempotency key. If the user changes their rating, posting the same `score_id` with a new value updates the record; it doesn't create a duplicate.
- In production this score would be written from a UI event handler (user clicks stars/thumbs), not from a script — but `create_score()` is the same call either way.

**✋ Check in**: "Do you see both scores? Does the `score_id` on the NUMERIC score make sense as an idempotency key?"

---

## Completion check

- [ ] Script ran without errors and printed a trace ID
- [ ] Trace appears in Langfuse UI filtered by tag `demo-1`
- [ ] `contains_email` BOOLEAN score is visible with correct value and comment
- [ ] `user_feedback` NUMERIC score is visible with `score_id` and value `4`

"You've attached scores to a live trace from application code — no eval pipeline, no annotation queue. Lab 2 turns this single-trace pattern into a repeatable test suite you can run against a fixed dataset on every deploy. Ready?"
