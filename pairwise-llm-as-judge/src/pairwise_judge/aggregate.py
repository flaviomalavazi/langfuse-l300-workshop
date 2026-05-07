"""Aggregate pairwise verdicts into win/tie/loss tallies and run-level scores.

Following the survey paper: pairwise LLM-as-a-judge is reported as
win/tie/loss counts and a win-rate. We also surface the position-conflict rate
as a diagnostic on the judge itself — high conflict means the judge is
position-biased on this dataset and the verdicts should be trusted less.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from langfuse import get_client

from .experiments import CandidateRun
from .judge import PairwiseDecision


@dataclass
class PairwiseSummary:
    n: int
    a_wins: int
    b_wins: int
    ties: int
    position_conflicts: int

    @property
    def a_win_rate(self) -> float:
        return self.a_wins / self.n if self.n else 0.0

    @property
    def b_win_rate(self) -> float:
        return self.b_wins / self.n if self.n else 0.0

    @property
    def tie_rate(self) -> float:
        return self.ties / self.n if self.n else 0.0

    @property
    def position_conflict_rate(self) -> float:
        return self.position_conflicts / self.n if self.n else 0.0

    @property
    def a_score(self) -> float:
        """Win rate counting ties as half a win — the standard win-rate-with-ties.

        With only A vs. B this is equivalent to (a_wins + 0.5 * ties) / n,
        the maximum-likelihood Bradley-Terry estimate when each pair is
        compared exactly once.
        """
        return (self.a_wins + 0.5 * self.ties) / self.n if self.n else 0.0

    @property
    def b_score(self) -> float:
        return (self.b_wins + 0.5 * self.ties) / self.n if self.n else 0.0


def summarize(decisions: list[tuple[str, PairwiseDecision]]) -> PairwiseSummary:
    a = b = t = c = 0
    for _, d in decisions:
        if d.verdict == "A":
            a += 1
        elif d.verdict == "B":
            b += 1
        else:
            t += 1
        if d.position_conflict:
            c += 1
    return PairwiseSummary(
        n=len(decisions), a_wins=a, b_wins=b, ties=t, position_conflicts=c
    )


def attach_run_scores(
    run_a: CandidateRun,
    run_b: CandidateRun,
    summary: PairwiseSummary,
) -> None:
    """Write run-level scores onto every trace in each run.

    Langfuse scores attach to traces (or sessions/observations), not to dataset
    runs directly, so we replicate the run-level metrics on each trace in the
    run. They show up consistently when filtering by run name in the UI.
    """
    langfuse = get_client()

    for out in run_a.outputs:
        langfuse.create_score(
            name="run_win_rate",
            value=summary.a_score,
            data_type="NUMERIC",
            trace_id=out.trace_id,
            comment=f"vs {run_b.run_name}; ties=0.5",
            metadata={"run_name": run_a.run_name, **asdict(summary)},
        )
        langfuse.create_score(
            name="judge_position_conflict_rate",
            value=summary.position_conflict_rate,
            data_type="NUMERIC",
            trace_id=out.trace_id,
            comment="Fraction of items where the swap-pass disagreed with the forward pass.",
        )

    for out in run_b.outputs:
        langfuse.create_score(
            name="run_win_rate",
            value=summary.b_score,
            data_type="NUMERIC",
            trace_id=out.trace_id,
            comment=f"vs {run_a.run_name}; ties=0.5",
            metadata={"run_name": run_b.run_name, **asdict(summary)},
        )
        langfuse.create_score(
            name="judge_position_conflict_rate",
            value=summary.position_conflict_rate,
            data_type="NUMERIC",
            trace_id=out.trace_id,
        )

    langfuse.flush()


def format_report(
    run_a: CandidateRun, run_b: CandidateRun, summary: PairwiseSummary
) -> str:
    return (
        f"Pairwise comparison: {run_a.run_name}  vs  {run_b.run_name}\n"
        f"  items judged           : {summary.n}\n"
        f"  A wins                 : {summary.a_wins} ({summary.a_win_rate:.1%})\n"
        f"  B wins                 : {summary.b_wins} ({summary.b_win_rate:.1%})\n"
        f"  ties                   : {summary.ties} ({summary.tie_rate:.1%})\n"
        f"  win-rate (ties=0.5)    : A={summary.a_score:.3f}  B={summary.b_score:.3f}\n"
        f"  position conflict rate : {summary.position_conflict_rate:.1%}\n"
    )
