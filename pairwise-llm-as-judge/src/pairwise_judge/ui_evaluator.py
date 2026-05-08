"""SDK equivalent of the UI's 'Run Experiment' wizard for the pairwise judge.

This module:
  1. Creates / updates the pairwise-judge chat prompt in Langfuse Prompt
     Management with the JSON schema for structured outputs stored in the
     prompt's config under the key 'pairwise-evaluator-output-schema'.
  2. Triggers a single dataset run of that judge against the combined
     dataset, using claude-haiku-4-5-20251001 with Anthropic tool-use to
     enforce the schema.

Why the schema lives in prompt.config:
  The Langfuse public REST API does not yet expose Playground-style
  structured-output schemas as first-class entities (see
  github.com/orgs/langfuse/discussions/9131). Storing the schema inside the
  prompt's config dict is the closest SDK-accessible equivalent: the schema
  is versioned alongside the prompt, retrievable via `langfuse.get_prompt`,
  and visible in the Langfuse UI on the prompt's config tab.
"""

from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic
from langfuse import get_client

from .config import Config

JUDGE_PROMPT_NAME = "pairwise-evaluator"
OUTPUT_SCHEMA_NAME = "pairwise-evaluator-output-schema"

# JSON schema for the judge's verdict. Mirrors the variables produced by the
# evaluator prompt: a categorical verdict, the actual model name (tag), and
# a short justification.
JUDGE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["A", "B", "tie"],
            "description": "Which response is better overall.",
        },
        "winning_model": {
            "type": "string",
            "description": (
                "The model identifier (from input.model_a / input.model_b) "
                "of the winning response, or the literal string 'tie'."
            ),
        },
        "reason": {
            "type": "string",
            "description": "One or two sentences justifying the verdict.",
        },
    },
    "required": ["verdict", "winning_model", "reason"],
    "additionalProperties": False,
}

# Chat prompt with placeholders matched to the combined dataset's input
# fields. The template references {{model_a}} and {{model_b}} so the judge
# can tag its verdict with the actual producing model.
JUDGE_PROMPT_MESSAGES = [
    {
        "role": "system",
        "content": (
            "You are an impartial judge comparing two AI assistant responses "
            "to the same user question.\n\n"
            "Metadata for tagging the verdict (do not let model identity bias "
            "your judgement):\n"
            "- Response A was produced by: {{model_a}}\n"
            "- Response B was produced by: {{model_b}}\n\n"
            "Evaluate the two responses on:\n"
            "1. Helpfulness — does it actually answer the question?\n"
            "2. Correctness — is it factually accurate?\n"
            "3. Clarity — is it well-structured and easy to follow?\n"
            "4. Conciseness — is it free of unnecessary padding?\n\n"
            "Choose the better response on overall quality. Use 'tie' only "
            "when the two responses are roughly equivalent. Do not let "
            "response order, length alone, or formatting style bias you.\n\n"
            "After deciding, tag the verdict with the producing model's name "
            "from the metadata above:\n"
            "- if verdict == 'A', winning_model is {{model_a}}\n"
            "- if verdict == 'B', winning_model is {{model_b}}\n"
            "- if verdict == 'tie', winning_model is 'tie'\n\n"
            "Respond by calling the submit_verdict tool with the structured "
            "verdict. Do not produce any free-form text."
        ),
    },
    {
        "role": "user",
        "content": (
            "[User question]\n{{question}}\n\n"
            "[Response A]\n{{response_a}}\n\n"
            "[Response B]\n{{response_b}}"
        ),
    },
]


def ensure_judge_prompt(model: str = "claude-haiku-4-5-20251001"):
    """Create / update the pairwise-evaluator prompt in Langfuse.

    The output schema is embedded in the prompt's config under the key
    `pairwise-evaluator-output-schema` so it is versioned with the prompt
    and retrievable in a single get_prompt call.
    """
    langfuse = get_client()
    prompt_config = {
        "model": model,
        "provider": "anthropic",
        "temperature": 0,
        # Named structured-output schema — keyed by name so future runners
        # (UI or SDK) can fetch it by the same string.
        OUTPUT_SCHEMA_NAME: JUDGE_OUTPUT_SCHEMA,
    }
    return langfuse.create_prompt(
        name=JUDGE_PROMPT_NAME,
        type="chat",
        prompt=JUDGE_PROMPT_MESSAGES,
        labels=["production"],
        config=prompt_config,
        commit_message=(
            "Pairwise judge prompt with structured-output schema for verdict + "
            "winning_model tag."
        ),
    )


def _render_messages(prompt_messages: list[dict], variables: dict[str, str]) -> tuple[str, list[dict]]:
    """Resolve {{var}} placeholders. Returns (system_prompt, user_messages)."""
    system_parts: list[str] = []
    user_messages: list[dict] = []
    for msg in prompt_messages:
        content = msg["content"]
        for k, v in variables.items():
            content = content.replace(f"{{{{{k}}}}}", str(v))
        if msg["role"] == "system":
            system_parts.append(content)
        else:
            user_messages.append({"role": msg["role"], "content": content})
    return "\n\n".join(system_parts), user_messages


def _judge_one_item(
    *,
    anthropic_client: Anthropic,
    item_input: dict[str, Any],
    prompt_messages: list[dict],
    model: str,
) -> dict[str, Any]:
    """Run the judge on one combined dataset item. Returns parsed verdict dict."""
    system_prompt, user_messages = _render_messages(prompt_messages, item_input)

    response = anthropic_client.messages.create(
        model=model,
        max_tokens=512,
        system=system_prompt,
        messages=user_messages,
        tools=[
            {
                "name": "submit_verdict",
                "description": "Submit the pairwise verdict.",
                "input_schema": JUDGE_OUTPUT_SCHEMA,
            }
        ],
        tool_choice={"type": "tool", "name": "submit_verdict"},
    )

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_verdict":
            return dict(block.input)

    raise RuntimeError(
        f"Judge did not produce a tool_use block. Raw content: {response.content!r}"
    )


def run_pairwise_evaluator_experiment(
    cfg: Config,
    combined_dataset_name: str,
    model: str = "claude-haiku-4-5-20251001",
    run_name: str | None = None,
):
    """Trigger one SDK-driven run of the pairwise evaluator on the combined dataset.

    Mirrors the UI 'Run Experiment' flow: a chat prompt + structured output
    schema + model, executed on every dataset item, with one trace per item
    and a categorical score per verdict.
    """
    import time

    langfuse = get_client()
    dataset = langfuse.get_dataset(combined_dataset_name)
    anthropic_client = Anthropic()

    # Re-fetch the prompt so we exercise the same fetch path the UI uses.
    prompt = langfuse.get_prompt(JUDGE_PROMPT_NAME, label="production")
    prompt_messages = prompt.prompt
    schema_from_config = (prompt.config or {}).get(OUTPUT_SCHEMA_NAME)
    if schema_from_config != JUDGE_OUTPUT_SCHEMA:
        print(
            f"[warn] schema in prompt.config['{OUTPUT_SCHEMA_NAME}'] differs from "
            "JUDGE_OUTPUT_SCHEMA in code. Using the code-side schema for tool input."
        )

    suffix = time.strftime("%Y%m%d-%H%M%S")
    name = run_name or f"{JUDGE_PROMPT_NAME}-{model}-{suffix}"

    def task(*, item, **_kwargs) -> dict[str, Any]:
        item_input = item["input"] if isinstance(item, dict) else item.input
        with get_client().start_as_current_observation(
            name=JUDGE_PROMPT_NAME, as_type="generation"
        ) as obs:
            verdict = _judge_one_item(
                anthropic_client=anthropic_client,
                item_input=item_input,
                prompt_messages=prompt_messages,
                model=model,
            )
            obs.update(
                input=item_input,
                output=verdict,
                model=model,
                metadata={"prompt_version": prompt.version, "schema_name": OUTPUT_SCHEMA_NAME},
                prompt=prompt,
            )

            # Categorical score on the verdict (A / B / tie) and a separate
            # score keyed by the actual winning model id so the leaderboard
            # groups by real model rather than anonymous A/B label.
            langfuse.score_current_trace(
                name="pairwise_outcome_ui",
                value=str(verdict["verdict"]),
                data_type="CATEGORICAL",
                comment=verdict.get("reason", "")[:200],
            )
            langfuse.score_current_trace(
                name="pairwise_winning_model",
                value=str(verdict["winning_model"]),
                data_type="CATEGORICAL",
            )
            return verdict

    print(
        f"[ui-judge] running '{name}' on {len(dataset.items)} items "
        f"(model={model}, prompt={JUDGE_PROMPT_NAME} v{prompt.version})"
    )
    result = dataset.run_experiment(
        name=name,
        description=(
            f"Pairwise judge run via SDK using prompt '{JUDGE_PROMPT_NAME}' "
            f"v{prompt.version} and schema '{OUTPUT_SCHEMA_NAME}'."
        ),
        task=task,
        max_concurrency=4,
        metadata={
            "model": model,
            "provider": "anthropic",
            "prompt_name": JUDGE_PROMPT_NAME,
            "prompt_version": str(prompt.version),
            "schema_name": OUTPUT_SCHEMA_NAME,
        },
    )
    langfuse.flush()
    return result
