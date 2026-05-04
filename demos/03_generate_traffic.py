"""
DEMO 3 — Seed production-style traffic for the LLM-as-a-judge demo.

Goal
----
Generate ~20 traces tagged `workshop` and `judge-demo` so that an LLM-as-a-
judge evaluator configured in the UI (filtering on those tags) has a fresh
set of targets to score. This is the setup step that the live demo runs a
minute before the presenter opens the Evaluators UI.

Run this once at the start of PART 4. By the time you finish explaining the
judge setup on the slide, the traces will be in the UI and the judge's first
run will have work to do.

Docs verified 2026-04:
  https://langfuse.com/docs/observability/features/sessions
  https://langfuse.com/docs/observability/features/users

Run:
    python 03_generate_traffic.py
"""

import os
import random
import time

from langfuse import get_client
from langfuse.openai import openai

langfuse = get_client()
client = openai.OpenAI()

# A mix of easy / hard / ambiguous questions so the judge's scores vary.
QUESTIONS = [
    "How do I reset my password?",
    "What is your refund policy?",
    "Why is my bill higher this month?",
    "Can you recommend a pizza place nearby?",          # off-topic
    "Is it raining in Berlin right now?",               # unknowable
    "How do I cancel my subscription?",
    "What plans do you offer?",
    "Explain quantum entanglement in 2 sentences.",     # off-topic
    "Do you ship to Brazil?",
    "What is the status of order #A-4821?",             # needs tool use
    "Can I pay by bank transfer?",
    "My invoice is wrong, what do I do?",
    "When was your company founded?",
    "Who is your CEO?",
    "Is there a student discount?",
    "Tell me a joke.",                                  # off-topic
    "What's the difference between the Pro and Team plans?",
    "I was charged twice for the same order.",
    "How long does delivery take to the UK?",
    "Can you send me a quote for 50 seats?",
]


def handle_one(question: str) -> None:
    user_id = f"demo-user-{random.randint(100, 999)}"
    with langfuse.start_as_current_span(name="support-assistant") as span:
        span.update_trace(
            user_id=user_id,
            session_id=f"sess-{user_id}-{int(time.time())}",
            tags=["workshop", "judge-demo"],
            input={"question": question},
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Acme Corp support. Answer only Acme-related "
                        "questions. If the question is unrelated, politely "
                        "decline."
                    ),
                },
                {"role": "user", "content": question},
            ],
        )
        answer = (resp.choices[0].message.content or "").strip()
        span.update_trace(output={"answer": answer})


def main() -> None:
    print(f"Seeding {len(QUESTIONS)} traces tagged 'workshop' + 'judge-demo'…")
    for i, q in enumerate(QUESTIONS, 1):
        handle_one(q)
        print(f"  [{i:>2}/{len(QUESTIONS)}] {q[:60]}")
    langfuse.flush()
    print("\nDone. In the Langfuse UI:")
    print("  1. Tracing → filter by tag 'judge-demo' → confirm traces.")
    print("  2. Evaluations → New evaluator → point at the same filter.\n")


if __name__ == "__main__":
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "OPENAI_API_KEY"):
        if not os.environ.get(k):
            raise SystemExit(f"Missing env var: {k}. See demos/README.md.")
    main()
