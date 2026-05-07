"""Pairwise LLM judge with positional-bias mitigation.

Methodology (from arxiv:2411.15594, "A Survey on LLM-as-a-Judge"):
- Compare two responses A and B to the same prompt.
- Position bias: a judge can prefer whichever response is shown first.
  Mitigation = run the comparison twice with sides swapped (Wang et al.) and
  resolve disagreement as a tie (PandaLM-style).
- Force structured output so verdicts can be parsed deterministically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from langfuse import get_client
from langfuse.openai import OpenAI

Verdict = Literal["A", "B", "tie"]

_JUDGE_SYSTEM_PROMPT = """You are an impartial judge evaluating two AI assistant responses to the same user question.

Compare the two responses on:
1. Helpfulness — does it actually answer the question?
2. Correctness — is it factually accurate?
3. Clarity — is it well-structured and easy to follow?
4. Conciseness — is it free of unnecessary padding?

You MUST respond with a single JSON object, no prose, no markdown fences:
{"verdict": "A" | "B" | "tie", "reason": "<one or two sentences>"}

Use "tie" only when the two responses are roughly equivalent in quality.
Do not let response order, length alone, or formatting style bias you.
"""

_USER_TEMPLATE = """[User question]
{question}

[Response A]
{response_a}

[Response B]
{response_b}
"""


@dataclass
class PairwiseDecision:
    """One full pairwise comparison after both passes."""

    verdict: Verdict  # final verdict after swap mitigation
    forward_verdict: Verdict  # A=left, B=right pass
    swapped_verdict: Verdict  # B=left, A=right pass (re-mapped back to A/B labels)
    position_conflict: bool  # the two passes disagreed
    forward_reason: str
    swapped_reason: str


def _parse_verdict(raw: str) -> tuple[Verdict, str]:
    """Best-effort JSON parse. Returns (verdict, reason)."""
    try:
        data = json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```"))
    except json.JSONDecodeError:
        # Last-ditch: scan the raw text for an A/B/tie token.
        lowered = raw.lower()
        if '"a"' in lowered or "verdict: a" in lowered:
            return "A", raw[:200]
        if '"b"' in lowered or "verdict: b" in lowered:
            return "B", raw[:200]
        return "tie", f"unparseable judge output: {raw[:200]}"

    verdict = str(data.get("verdict", "tie")).strip().lower()
    if verdict not in ("a", "b", "tie"):
        verdict = "tie"
    return verdict.upper() if verdict != "tie" else "tie", str(data.get("reason", ""))  # type: ignore[return-value]


def _judge_once(*, question: str, left: str, right: str, model: str) -> tuple[Verdict, str]:
    """Single judge call. `left` is shown as Response A, `right` as Response B."""
    response = OpenAI().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _USER_TEMPLATE.format(
                    question=question, response_a=left, response_b=right
                ),
            },
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    return _parse_verdict(raw)


def judge_pair(
    *,
    question: str,
    response_a: str,
    response_b: str,
    judge_model: str,
) -> PairwiseDecision:
    """Two-pass pairwise judge.

    Pass 1 (forward): A on the left, B on the right.
    Pass 2 (swapped): B on the left, A on the right; the verdict is then
    re-mapped back to A/B space so "left wins" in pass 2 means B wins overall.
    If the two passes disagree we record a tie (PandaLM convention).
    """
    with get_client().start_as_current_observation(name="pairwise-judge") as obs:
        forward, fwd_reason = _judge_once(
            question=question, left=response_a, right=response_b, model=judge_model
        )

        swapped_raw, swp_reason = _judge_once(
            question=question, left=response_b, right=response_a, model=judge_model
        )
        # Re-map: in the swapped pass, "A" means response_b actually won.
        swapped: Verdict = (
            "B" if swapped_raw == "A" else "A" if swapped_raw == "B" else "tie"
        )

        if forward == swapped:
            final = forward
            conflict = False
        elif forward == "tie" or swapped == "tie":
            # One pass is decisive, one is a tie — go with the decisive one but
            # flag a soft conflict so it shows up in the run-level metric.
            final = forward if forward != "tie" else swapped
            conflict = True
        else:
            # Hard disagreement (A vs B). PandaLM-style: call it a tie.
            final = "tie"
            conflict = True

        decision = PairwiseDecision(
            verdict=final,
            forward_verdict=forward,
            swapped_verdict=swapped,
            position_conflict=conflict,
            forward_reason=fwd_reason,
            swapped_reason=swp_reason,
        )

        obs.update(
            input={"question": question, "response_a": response_a, "response_b": response_b},
            output={
                "verdict": decision.verdict,
                "forward_verdict": decision.forward_verdict,
                "swapped_verdict": decision.swapped_verdict,
                "position_conflict": decision.position_conflict,
            },
            metadata={
                "forward_reason": decision.forward_reason,
                "swapped_reason": decision.swapped_reason,
            },
        )
        return decision
