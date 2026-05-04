# Lab 4: Annotation Queue (Bulk Assign) — Agent Instructions

> **For the attendee**: Paste this file's contents into your AI assistant, or say "start lab 4" if your assistant has already loaded `AGENTS.md`.

---

## Before we start

Tell the attendee:

> "Lab 4 is the final piece: human annotation. LLM judges are fast and cheap but not always right — human annotation queues provide the ground-truth layer that lets you calibrate (and eventually validate or replace) the judge.
>
> This lab requires a UI step **before** running the script. Don't run the script yet.
> Make sure your terminal is open in `demos/` and that you completed Lab 3 (the `judge-demo` traces must exist)."

---

## Your task

You are teaching Lab 4 as a live instructor. Walk the attendee through creating the annotation queue in the UI, then run the bulk-assignment script, then guide them to work one item end-to-end through the reviewer interface.

The goal: show how to go from "I have an interesting filter in the UI" to "the SME team has items to review" — without manual clicking.

---

## Step 1 — Understand annotation queues

**Announce**:

> "Let's understand what a queue is before we build one."

**Explain**: An annotation queue is a structured work queue for human reviewers. Each item is a trace (or observation) with a status (`PENDING`, `ACTIVE`, `DONE`). Reviewers open an item, see the full trace context, assign a score, optionally add a comment, and click Complete.

The human scores that come out of this queue are the **ground truth** for your eval pipeline:
- They're what you use to calibrate the LLM judge (Score Analytics — Cohen's κ).
- They're what you use to build labeled datasets for fine-tuning.
- They're what you show compliance teams as evidence of human oversight.

The routing challenge: you have thousands of traces, but reviewers only have time for a sample. You want to route the *right* traces — low-scoring, high-traffic, edge-case, or recently changed. Doing this manually (copy-pasting trace IDs) doesn't scale. The script in this lab automates the pattern using two REST API calls.

**Explain the REST-only approach**: The script uses only `requests` — no Langfuse Python SDK. This is intentional: it shows that annotation queues are accessible from any language or toolchain that can make HTTP calls. The auth is HTTP Basic with your public key as username and secret key as password. This is the same auth your CI pipeline would use.

**✋ Check in**: "Questions about the queue concept before we set one up?"

---

## Step 2 — UI prep: create the annotation queue

**Announce**: "You need to create the queue in the UI first. The script needs the queue ID."

**Walk the attendee through the UI**:

1. Go to **Annotation Queues** → click **New Queue**.
2. Name it `workshop-queue` (or any name you like).
3. Under **Score Config**, choose `helpfulness` — or create it now:
   - Go to **Score Configs** → **New**.
   - Name: `helpfulness`, type: NUMERIC, range: 0–1.
   - Save, then come back to the queue creation.
4. Add yourself as an assignee.
5. Click **Create**.
6. Copy the queue ID from the URL: it's the UUID in `/annotation-queues/<this-uuid>`.

**Paste the queue ID into `.env`**:

```bash
# In demos/.env, add:
LANGFUSE_QUEUE_ID=<paste-the-uuid-here>
```

**Verify it's set**:

```bash
grep -E '^LANGFUSE_QUEUE_ID=' .env
```

> Do not proceed until `LANGFUSE_QUEUE_ID` is in `.env` — the script will exit immediately if it's missing.

**✋ Check in**: "Do you have the queue created and `LANGFUSE_QUEUE_ID` set in `.env`?"

---

## Step 3 — Walk through the script

**Announce**: "Now let's read the script before running."

**Show the script** — open [lab04/04_bulk_assign_to_queue.py](04_bulk_assign_to_queue.py) or run:

```bash
cat lab04/04_bulk_assign_to_queue.py
```

**Point out**:

1. **Two API calls only** — `GET /api/public/traces` (query) and `POST /api/public/annotation-queues/{queueId}/items` (assign). That's the full integration. Everything else is filtering and printing.
2. `list_candidate_traces()` — queries traces tagged `judge-demo` from the last 24 hours. The `fromTimestamp` keeps the filter narrow; for large corpora add `page` + `limit` pagination.
3. The `# GAP:` comment — the public API only shows `"TRACE"` as an example value for `objectType`. `"OBSERVATION"` and `"SESSION"` exist in the Langfuse source but are not publicly documented. The workshop uses `"TRACE"` only.
4. `assign_trace_to_queue()` — POSTs `{"objectId": trace_id, "objectType": "TRACE"}` to the queue endpoint. A `409 Conflict` means the trace is already in the queue — treated as a skip, not an error.
5. HTTP Basic auth via `AUTH = (PUBLIC_KEY, SECRET_KEY)` — same credentials as the SDK, just used directly in `requests`.

**✋ Check in**: "Does the two-call structure make sense? Any questions about the auth pattern?"

---

## Step 4 — Run the script

**Terminal prompt**: "In `demos/`, run:"

```bash
uv run lab04/04_bulk_assign_to_queue.py
```

**Expected output**:

```
Found 20 candidate traces.
  ✓ <trace-id-1> → queue item <item-id>
  ✓ <trace-id-2> → queue item <item-id>
  ...
Summary: 20 assigned, 0 skipped.
Open the queue in Langfuse UI: https://<your-host>/annotation-queues/<queue-id>
```

**If the script fails**:
- `Missing env var: LANGFUSE_QUEUE_ID` → go back to Step 2.
- `Found 0 candidate traces` → Lab 3 traces are older than 24 hours, or `LANGFUSE_HOST` points at the wrong region. If older: change `timedelta(hours=24)` to `timedelta(days=7)` temporarily and re-run.
- `404 Not Found` on the POST → the queue ID is wrong; double-check it against the URL in the UI.
- `409 Conflict` on all items → traces were already added to the queue (safe to ignore; re-running is idempotent by accident).

**✋ Check in**: "Did the script complete? How many were assigned?"

---

## Step 5 — Work one item end-to-end

**Announce**: "Now let's actually use the queue as a reviewer would."

**Langfuse check**:

1. Go to **Annotation Queues** → open `workshop-queue`.
2. You should see items with status `PENDING`.
3. Click **Start reviewing** (or open one item).

**Walk through the reviewer interface**:

- The reviewer sees the full trace: every span, every score already attached (including the judge's `helpfulness` score from Lab 3).
- Assign a `helpfulness` score between 0 and 1 based on what you read.
- Add a comment explaining your reasoning (especially for borderline scores).
- Click **Complete**.

**After completing one item**:

1. Navigate to **Tracing** → find the trace you just reviewed (use the trace ID from the queue item).
2. Open the **Scores** panel.

**What to point out**:

- The human `helpfulness` score now appears **alongside** the judge's `helpfulness` score in the Scores panel. This side-by-side view is the input to Score Analytics.
- The human comment is preserved and visible — this is what calibration reviewers use when they disagree with the judge.
- The trace now has provenance from three sources: the app (Lab 1 pattern — programmatic scores), the LLM judge (Lab 3 — automated), and a human reviewer (this lab). That's the full signal stack.

**✋ Check in**: "Do you see the human score alongside the judge score on the same trace?"

---

## Step 6 — Score Analytics calibration preview

**Announce**: "One last thing — where this all leads."

**Langfuse check**:

1. Go to **Score Analytics** in the Langfuse UI.
2. Select two scores of the same name (`helpfulness`) and compare the judge scores against the human scores.
3. Look at the agreement matrix and Cohen's κ.

**Explain**:

- κ > 0.6 = the judge is useful as a signal
- κ > 0.8 = the judge can serve as the primary quality gate
- κ < 0.4 = rework the rubric — the judge is disagreeing with humans too often to trust

In a real calibration workflow you'd review ~50–100 traces, compute κ, iterate on the rubric, re-score, and repeat until κ > 0.6. The annotation queue is what makes this scalable: you write the routing logic once and reviewers just work their queue.

**✋ Check in**: "Does the Score Analytics calibration loop make sense as a workflow?"

---

## Completion check

- [ ] Annotation queue `workshop-queue` created with `helpfulness` score config
- [ ] `LANGFUSE_QUEUE_ID` set in `.env`
- [ ] Script ran and assigned traces to the queue
- [ ] Worked one item end-to-end: scored it, added a comment, clicked Complete
- [ ] Human score appears alongside judge score on the same trace in Tracing
- [ ] You understand how Score Analytics / Cohen's κ closes the calibration loop

"You've now wired up all four sources of scores: programmatic guardrails, offline experiments, an LLM judge, and human annotation. The next step is to calibrate the judge against the human scores in Score Analytics — see slide 22 in the deck. See you in the Q&A!"
