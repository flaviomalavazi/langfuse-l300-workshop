# Lab 3: LLM-as-a-Judge (Seed Traffic) — Agent Instructions

> **For the attendee**: Paste this file's contents into your AI assistant, or say "start lab 3" if your assistant has already loaded `AGENTS.md`.

---

## Before we start

Tell the attendee:

> "Labs 1 and 2 produced scores from code. Lab 3 introduces a different source: the Langfuse backend's LLM-as-a-judge evaluator, which scores live traces automatically — no code change to your application needed.
>
> This lab has two parts: first we seed ~20 traces by running a script, then we configure the judge evaluator in the UI. Make sure your terminal is open in `demos/`."

---

## Your task

You are teaching Lab 3 as a live instructor. Explain the LLM-as-a-judge pattern, run the traffic-seeding script, then walk the attendee through the UI steps to configure the judge. Finally, show them how to read the judge's own trace for debugging.

The goal: understand that an LLM judge is itself an observable, debuggable LLM call — and see it score a corpus of deliberately varied traces.

---

## Step 1 — Understand LLM-as-a-judge

**Announce**:

> "Before running the script, let's understand what we're setting up."

**Explain**: An LLM-as-a-judge evaluator runs inside the Langfuse backend on a schedule. It reads existing traces that match a filter, runs a rubric prompt against the input/output of each span, and writes scores back to those traces — no change to your application code required.

The key choices when configuring a judge:

- **Target: Live observations** (not traces). The judge scores individual spans, not the trace root — this is where `input` and `output` live.
- **Filter**: `tag = judge-demo`. This scopes the judge to workshop traces only.
- **Sampling: 25%**. Keeps cost and latency down; set to 100% in production CI.
- **Variable mapping**: `{{input}}` → span's input field, `{{output}}` → span's output field. Template variables must match field names exactly.

The corpus needs to be **varied** — a flat score distribution makes calibration impossible. This script deliberately mixes easy support questions, off-topic questions, and unanswerable requests so the judge's scores will spread across the range.

**Explain the tracing pattern** in this script — it's the same v4 pattern from Lab 1:
- `propagate_attributes()` sets trace identity (`user_id`, `session_id`, `tags`, `trace_name`).
- `start_as_current_observation()` creates the span.
- Two `span.update()` calls: one for input before the model call, one for output after. This is intentional — in production you capture input before the call so that if the model throws, you still have the input recorded.

**✋ Check in**: "Questions about how the judge evaluator works before we seed the data?"

---

## Step 2 — Walk through the script

**Announce**: "Let's look at the script quickly."

**Show the script** — open [lab03/03_generate_traffic.py](03_generate_traffic.py) or run:

```bash
cat lab03/03_generate_traffic.py
```

**Point out**:

1. `QUESTIONS` list — 20 prompts deliberately mixing easy (password reset), off-topic (pizza place, quantum entanglement, jokes), and unanswerable (order #A-4821 needs tool access). This variance is what makes the judge useful to calibrate.
2. `propagate_attributes(tags=["workshop", "judge-demo"], ...)` — the `judge-demo` tag is what the UI filter will use. Both tags are set so the traces show up under workshop filtering too.
3. `session_id=f"sess-{user_id}-{int(time.time())}"` — each trace gets a unique session; this simulates independent users so the data looks like real traffic.
4. Two `span.update()` calls — `span.update(input=...)` before the model call, `span.update(output=...)` after. Deliberate: captures input even if the model call throws.

**✋ Check in**: "Any questions about why the question corpus is deliberately varied?"

---

## Step 3 — Run the script

**Terminal prompt**: "In `demos/`, run:"

```bash
uv run lab03/03_generate_traffic.py
```

**Expected output**:

```
Seeding 20 traces tagged 'workshop' + 'judge-demo'…
  [ 1/20] How do I reset my password?
  [ 2/20] What is your refund policy?
  ...
  [20/20] Can you send me a quote for 50 seats?

Done. In the Langfuse UI:
  1. Tracing → filter by tag 'judge-demo' → confirm traces.
  2. Evaluations → New evaluator → point at the same filter.
```

**If the script fails**:
- `Missing env var` → check `.env`.
- Rate limit from OpenAI → the script runs sequentially (one trace at a time), so this is rare unless the API key has very low quota.

**✋ Check in**: "Did all 20 traces seed successfully?"

---

## Step 4 — Verify traces in the UI

**Announce**: "Let's confirm the traces landed before setting up the judge."

**Langfuse check**:

1. Go to **Tracing** in the Langfuse UI.
2. Filter by tag `judge-demo`.
3. You should see 20 new traces named `advanced-support-assistant`.

**What to point out**:

- Open one trace. Click the span — the `input` (question) and `output` (answer) fields are both populated.
- Notice off-topic questions like "Tell me a joke" or "Can you recommend a pizza place nearby?" — the model politely declines. These are the traces that should score *low* on helpfulness.
- Notice the `user_id` on each trace — different users simulated distinct support sessions.

**✋ Check in**: "Do you see 20 traces? Open one off-topic trace — does the model decline appropriately?"

---

## Step 5 — Configure the LLM judge evaluator

**Announce**: "Now the UI configuration. I'll guide you through it step by step — don't click ahead."

**Walk the attendee through the UI**:

1. Go to **Evaluations** → click **New Evaluator**.
2. Under **Managed templates**, choose **Helpfulness** (or any numeric/boolean managed template).
3. Set **Target** to `Live observations` (not Traces — this is critical; observations are where `input`/`output` live).
4. Add **Filter**: `tag = judge-demo`.
5. Set **Sampling** to `25%` (fast for workshop; use 100% in production).
6. Map `{{input}}` to the span's `input` field and `{{output}}` to the span's `output` field.
7. Click **Save**.

**After saving**: wait ~30 seconds. The judge runs asynchronously — scores will start appearing on the seeded traces.

> If the judge doesn't fire: check that the filter is `tag = judge-demo` (not `tags`), and that you targeted **observations**, not traces.

**✋ Check in**: "Did the judge configuration save? Are you seeing scores start to appear on the traces?"

---

## Step 6 — Read the judge's own trace

**Announce**: "Here's the part most teams miss — the judge is debuggable."

**Langfuse check**:

1. Go to **Tracing**.
2. Switch the **Environment** filter to `langfuse-llm-as-a-judge`.
3. Open one of the judge's own traces.

**What to point out**:

- The judge's LLM call is itself a traced generation — you can see the latency, token cost, and the **full rendered prompt** including the rubric and the evaluated span's input/output.
- This is what "the judge is debuggable" means: if you get unexpected scores, open the judge's trace, read the rendered prompt, and you'll see exactly what it was given. Most rubric failures come from unexpected formatting in `input`/`output`.
- Open a trace that scored low and check the judge's reasoning string. The reasoning is the most important output — it tells you *why* the judge scored the way it did and whether the rubric needs tightening.

**✋ Check in**: "Can you find the judge's own trace? Read the reasoning on a low-scoring trace — does the rubric make sense?"

---

## Completion check

- [ ] 20 traces seeded, visible in UI under tag `judge-demo`
- [ ] LLM judge evaluator configured with `tag = judge-demo` filter and `observations` target
- [ ] Scores start landing on seeded traces after ~30 seconds
- [ ] You opened the judge's own trace and read the reasoning field
- [ ] Off-topic questions scored lower than on-topic support questions

"The judge is wired up and scoring live traffic. Lab 4 adds the human layer: an annotation queue that routes the same traces to domain experts for ground-truth review. That's how you calibrate and eventually validate the judge. Ready?"
