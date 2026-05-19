"""Research pipe closure checks.

No 'complete' state without closure evidence. This module provides
validation helpers that enforce the closure invariant.

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

from research_pipe.models import ResearchJob, TERMINAL_STATES


class IncompleteClosureError(Exception):
    """Raised when closure evidence is insufficient."""


def validate_closure(job: ResearchJob) -> list[str]:
    """Check whether a job's closure evidence is sufficient.

    Returns a list of problems (empty = clean).
    """
    problems: list[str] = []

    if job.state not in TERMINAL_STATES:
        problems.append(f"Job is in non-terminal state '{job.state}'.")
        return problems

    if job.lift_result is None:
        problems.append("Terminal state reached without a LiftResult.")
        return problems

    if not job.lift_result.summary.strip():
        problems.append("LiftResult has an empty summary.")

    if not job.lift_result.decided_by.strip():
        problems.append("LiftResult has no decided_by attribution.")

    return problems


def assert_closure(job: ResearchJob) -> None:
    """Raise if closure evidence is missing or incomplete."""
    problems = validate_closure(job)
    if problems:
        raise IncompleteClosureError(
            f"Job '{job.job_id}' has closure problems: {'; '.join(problems)}"
        )
