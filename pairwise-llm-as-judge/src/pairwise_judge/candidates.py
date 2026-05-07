"""Candidate systems under test.

Each system is a small wrapper around an OpenAI chat completion. The two
systems differ in model and system-prompt so the judge has something real to
discriminate. The task functions wrap each call in a Langfuse observation
(via `start_as_current_observation`) so every run produces a trace that can
be linked back to the dataset item by `run_experiment`.
"""

from langfuse import get_client
from langfuse.openai import OpenAI

from .config import Config

_CONCISE_SYSTEM_PROMPT = (
    "You are a concise assistant. Answer in one or two sentences. "
    "Do not pad with caveats or preamble."
)

_DETAILED_SYSTEM_PROMPT = (
    "You are a careful assistant. Think step by step before answering and "
    "then give a thorough, well-structured response that explains the why."
)


def _extract_question(item) -> str:
    """`item` is either a dict (local data) or a DatasetItem (Langfuse).

    Local-data items expose `item["input"]`; DatasetItems expose `item.input`,
    which the SDK returns as whatever Python value was stored. We accept both
    a plain string and a `{"question": "..."}` dict for convenience.
    """
    raw = item["input"] if isinstance(item, dict) else item.input
    if isinstance(raw, dict):
        return raw.get("question") or raw.get("prompt") or raw.get("text") or str(raw)
    return str(raw)


def _run_chat(question: str, model: str, system_prompt: str) -> str:
    response = OpenAI().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content or ""


def make_system_a_task(cfg: Config):
    """Returns a task function suitable for `langfuse.run_experiment`."""

    def system_a(*, item, **_kwargs) -> str:
        question = _extract_question(item)
        with get_client().start_as_current_observation(name=cfg.system_a_name) as obs:
            output = _run_chat(question, cfg.system_a_model, _CONCISE_SYSTEM_PROMPT)
            obs.update(input=question, output=output)
            return output

    return system_a


def make_system_b_task(cfg: Config):
    def system_b(*, item, **_kwargs) -> str:
        question = _extract_question(item)
        with get_client().start_as_current_observation(name=cfg.system_b_name) as obs:
            output = _run_chat(question, cfg.system_b_model, _DETAILED_SYSTEM_PROMPT)
            obs.update(input=question, output=output)
            return output

    return system_b
