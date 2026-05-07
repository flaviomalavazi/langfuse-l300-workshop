"""Orchestration: generate System A and System B runs, then judge pairwise.

The flow:
  1. `run_candidate_experiment` calls `dataset.run_experiment(...)` for one
     system. The Langfuse SDK creates a dataset run, traces every task call,
     and links each trace to the originating dataset item.
  2. We capture each item's trace_id and output from the experiment result so
     we can later attach pairwise scores back to the right traces.
  3. `run_pairwise_judge` joins the two runs by dataset_item_id, calls
     `judge_pair` (two-pass swap), and writes scores to both traces.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from langfuse import get_client

from .candidates import make_system_a_task, make_system_b_task
from .config import Config
from .judge import PairwiseDecision, judge_pair


@dataclass
class CandidateOutput:
    dataset_item_id: str
    trace_id: str
    output: str


@dataclass
class CandidateRun:
    system_name: str
    run_name: str
    outputs: list[CandidateOutput]  # one per dataset item

    def by_item(self) -> dict[str, CandidateOutput]:
        return {o.dataset_item_id: o for o in self.outputs}


def _extract_outputs(experiment_result) -> list[CandidateOutput]:
    """Pull (dataset_item_id, trace_id, output) tuples from the SDK result.

    `experiment_result.item_results` is a list of `ExperimentItemResult`. When
    the experiment was run against a Langfuse dataset, `r.item` is a
    `DatasetItem` whose `id` is the dataset_item_id we need to join on. For
    local-data runs `r.item` is a plain dict and has no id — pairwise judging
    requires a Langfuse-hosted dataset, so we error loudly in that case.
    """
    outs: list[CandidateOutput] = []
    for r in experiment_result.item_results:
        item = r.item
        item_id = getattr(item, "id", None)
        if item_id is None or r.trace_id is None:
            raise RuntimeError(
                f"Experiment item missing dataset id or trace_id: {r!r}. "
                "Pairwise judging requires a Langfuse-hosted dataset."
            )
        outs.append(
            CandidateOutput(
                dataset_item_id=str(item_id),
                trace_id=str(r.trace_id),
                output=str(r.output) if r.output is not None else "",
            )
        )
    return outs


def run_candidate_experiment(
    cfg: Config, system: str, run_suffix: str | None = None
) -> CandidateRun:
    """Run one candidate system over the dataset and return its outputs.

    `system` must be "A" or "B".
    """
    langfuse = get_client()
    dataset = langfuse.get_dataset(cfg.dataset_name)

    suffix = run_suffix or time.strftime("%Y%m%d-%H%M%S")
    if system.upper() == "A":
        task = make_system_a_task(cfg)
        model = cfg.system_a_model
        run_name = f"{cfg.system_a_name}-{model}-{suffix}"
    elif system.upper() == "B":
        task = make_system_b_task(cfg)
        model = cfg.system_b_model
        run_name = f"{cfg.system_b_name}-{model}-{suffix}"
    else:
        raise ValueError(f"system must be 'A' or 'B', got {system!r}")

    print(f"[generate] {run_name} on {len(dataset.items)} items (model={model})")
    result = dataset.run_experiment(
        name=run_name,
        description=f"Candidate system {system.upper()} for pairwise evaluation.",
        task=task,
        max_concurrency=5,
        metadata={"system": system.upper(), "model": model},
    )
    langfuse.flush()
    return CandidateRun(
        system_name=cfg.system_a_name if system.upper() == "A" else cfg.system_b_name,
        run_name=run_name,
        outputs=_extract_outputs(result),
    )


def run_pairwise_judge(
    cfg: Config, run_a: CandidateRun, run_b: CandidateRun
) -> list[tuple[str, PairwiseDecision]]:
    """Judge each (A, B) pair and write scores. Returns [(item_id, decision)]."""
    langfuse = get_client()
    dataset = langfuse.get_dataset(cfg.dataset_name)

    a_by_item = run_a.by_item()
    b_by_item = run_b.by_item()

    decisions: list[tuple[str, PairwiseDecision]] = []
    for item in dataset.items:
        a = a_by_item.get(item.id)
        b = b_by_item.get(item.id)
        if a is None or b is None:
            print(f"[judge] skip item {item.id}: missing output (a={a is not None}, b={b is not None})")
            continue

        question = (
            item.input.get("question") if isinstance(item.input, dict) else str(item.input)
        )
        decision = judge_pair(
            question=question,
            response_a=a.output,
            response_b=b.output,
            judge_model=cfg.judge_model,
        )
        decisions.append((item.id, decision))

        # Map the verdict to a per-system categorical score, attached to each
        # candidate's trace so it shows up alongside the run in Langfuse.
        a_label = _verdict_label_for("A", decision.verdict)
        b_label = _verdict_label_for("B", decision.verdict)

        langfuse.create_score(
            name="pairwise_outcome",
            value=a_label,
            data_type="CATEGORICAL",
            trace_id=a.trace_id,
            comment=f"vs {run_b.run_name}: {decision.forward_reason[:200]}",
            metadata={
                "opponent_run": run_b.run_name,
                "opponent_trace_id": b.trace_id,
                "forward_verdict": decision.forward_verdict,
                "swapped_verdict": decision.swapped_verdict,
                "position_conflict": decision.position_conflict,
            },
        )
        langfuse.create_score(
            name="pairwise_outcome",
            value=b_label,
            data_type="CATEGORICAL",
            trace_id=b.trace_id,
            comment=f"vs {run_a.run_name}: {decision.forward_reason[:200]}",
            metadata={
                "opponent_run": run_a.run_name,
                "opponent_trace_id": a.trace_id,
                "forward_verdict": decision.forward_verdict,
                "swapped_verdict": decision.swapped_verdict,
                "position_conflict": decision.position_conflict,
            },
        )

    langfuse.flush()
    return decisions


def _verdict_label_for(side: str, verdict: str) -> str:
    """Translate the global verdict ('A'/'B'/'tie') into this side's outcome."""
    if verdict == "tie":
        return "tie"
    return "win" if verdict == side else "loss"
