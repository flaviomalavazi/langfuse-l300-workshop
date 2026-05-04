"""
DEMO 1 — Attaching scores to production traces from application code.

Goal
----
Show how to capture two kinds of signal on a live trace without any eval job:
  * a programmatic guardrail score (BOOLEAN)  — "did the answer leak an email?"
  * a user-feedback score (NUMERIC)           — simulated 1–5 stars from the UI

Both go through `langfuse.create_score()`, which is the low-level, stable
method that works from any context. For span-scoped variants see
`langfuse.score_current_span()` / `langfuse.score_current_trace()` in the docs.

Docs verified 2026-04:
  https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk

Run:
    python 01_scores_from_app.py
"""

import os
import re
import time
import uuid

from langfuse import get_client
from langfuse.openai import openai  # Langfuse-instrumented OpenAI wrapper

langfuse = get_client()
client = openai.OpenAI()

# Naive email detector — production should use a real guardrail library.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def ask_assistant(question: str) -> tuple[str, str]:
    """Run one user turn inside a Langfuse trace. Returns (answer, trace_id)."""
    with langfuse.start_as_current_span(name="assistant-turn") as span:
        span.update_trace(
            user_id="demo-user-123",
            session_id=f"workshop-session-{int(time.time() // 3600)}",
            tags=["workshop", "demo-1"],
            input={"question": question},
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a concise support assistant."},
                {"role": "user", "content": question},
            ],
        )
        answer = response.choices[0].message.content or ""
        span.update_trace(output={"answer": answer})
        trace_id = langfuse.get_current_trace_id()

    return answer, trace_id


def main() -> None:
    # A prompt that tempts the model to echo the email address back.
    question = "Summarize the SLA in the contract we just sent to acme@acme.com."
    answer, trace_id = ask_assistant(question)
    print(f"\nTrace: {trace_id}")
    print(f"Answer: {answer}\n")

    # --- Score 1: programmatic BOOLEAN guardrail ------------------------
    # For BOOLEAN, `value` MUST be 0 or 1 (float) AND `data_type` MUST be set
    # explicitly — otherwise the SDK infers NUMERIC from a numeric value.
    contains_email = bool(EMAIL_RE.search(answer))
    langfuse.create_score(
        name="contains_email",
        value=1 if contains_email else 0,
        data_type="BOOLEAN",
        trace_id=trace_id,
        comment="Auto-guardrail: regex scan of the final answer.",
    )
    print(f"[guardrail] contains_email = {contains_email}")

    # --- Score 2: simulated user feedback (NUMERIC, 1–5) ----------------
    # Pass a stable `score_id` so a retry upserts the same score instead of
    # adding a duplicate. (Python SDK uses `score_id`; JS/TS uses `id`.)
    # In production this score would be written from the UI handler when
    # the user clicks stars / thumbs.
    simulated_stars = 4
    langfuse.create_score(
        score_id=f"user-feedback-{uuid.uuid4()}",
        name="user_feedback",
        value=simulated_stars,
        data_type="NUMERIC",
        trace_id=trace_id,
        comment=f"User rated this {simulated_stars}/5 stars.",
    )
    print(f"[feedback] user_feedback = {simulated_stars}/5")

    # Flush so the audience sees the scores in the UI immediately.
    langfuse.flush()
    print("\nFlushed. Open the trace in Langfuse UI to see both scores.\n")


if __name__ == "__main__":
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "OPENAI_API_KEY"):
        if not os.environ.get(k):
            raise SystemExit(f"Missing env var: {k}. See demos/README.md.")
    main()
