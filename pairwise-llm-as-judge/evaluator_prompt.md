# Pairwise LLM-as-a-Judge — Langfuse UI Evaluator

This evaluator runs against the combined dataset produced by
`build_combined_dataset.py`. It scores each item by comparing the two
candidate responses and emits a categorical verdict plus the winning model's
name (so you can group results by model directly in the UI).

## Variable mapping

In the Langfuse UI, when configuring the evaluator, map the template
variables to these JSON paths on each dataset item:

| Variable     | JSON path             | Notes                              |
|--------------|-----------------------|------------------------------------|
| `model_a`    | `input.model_a`       | Model that produced response A     |
| `model_b`    | `input.model_b`       | Model that produced response B     |
| `question`   | `input.question`      | Original user question             |
| `response_a` | `input.response_a`    | Candidate A's answer               |
| `response_b` | `input.response_b`    | Candidate B's answer               |

The judge consumes three inputs as comparison material — the question, response A,
and response B. `model_a` / `model_b` are supplied as supplementary metadata so the
judge can tag its verdict with the actual model name.

## Prompt template

Paste the following into the evaluator prompt field. Langfuse will substitute
`{{var}}` placeholders from the variable mapping above.

```
You are an impartial judge comparing two AI assistant responses to the same user question.

Metadata for tagging the verdict (do not let the model identity bias your judgement):
- Response A was produced by: {{model_a}}
- Response B was produced by: {{model_b}}

Evaluate the two responses on:
1. Helpfulness — does it actually answer the question?
2. Correctness — is it factually accurate?
3. Clarity — is it well-structured and easy to follow?
4. Conciseness — is it free of unnecessary padding?

[User question]
{{question}}

[Response A]
{{response_a}}

[Response B]
{{response_b}}

Choose the better response on overall quality. Use "tie" only when the two
responses are roughly equivalent. Do not let response order, length alone,
or formatting style bias you.

After deciding, tag the verdict with the producing model's name from the
metadata above:
- if verdict == "A", winning_model is {{model_a}}
- if verdict == "B", winning_model is {{model_b}}
- if verdict == "tie", winning_model is "tie"

Reply with a SINGLE JSON object and nothing else (no markdown fences, no prose):

{
  "verdict": "A" | "B" | "tie",
  "winning_model": "<model name from metadata, or 'tie'>",
  "reason": "<one or two sentences justifying the verdict>"
}
```

## Suggested score configuration

Configure the evaluator output as a categorical score so you can filter and
aggregate in the UI:

- **Score name:** `pairwise_outcome_ui`
- **Data type:** `CATEGORICAL`
- **Categories:** `A`, `B`, `tie` (extracted from the `verdict` field)
- **Reasoning field:** `reason`

If the UI supports multiple scores per evaluator, also emit a second score
keyed on `winning_model` so the leaderboard groups results by actual model
identifier (e.g., `gpt-4o-mini` vs `gpt-4.1-mini`) rather than by anonymous
A/B labels.

## Mitigating position bias

The code-driven judge in `src/pairwise_judge/judge.py` runs each comparison
twice with sides swapped (PandaLM-style tie-on-conflict). The UI evaluator
runs once per item, so it does **not** mitigate position bias on its own. To
approximate the same protocol from the UI:

1. Run the evaluator once on the combined dataset as built.
2. Build a second combined dataset with `response_a` and `response_b` swapped
   (and `model_a` / `model_b` swapped along with them) and run the same
   evaluator on it.
3. Resolve disagreements between the two passes as ties.
