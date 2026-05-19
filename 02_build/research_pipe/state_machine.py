"""Research pipe state machine.

Enforces valid transitions only. No job reaches a terminal state
without closure evidence (a LiftResult).

States:
  intake_open
    → research_running
      → research_done_implementation_pending
        → implemented_verified | parked_verified | rejected_verified | no_action_verified

The pipe does not promote. It routes and tags. Promotion happens
outside via spine gates.

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

from research_pipe.models import (
    LiftResult,
    ResearchJob,
    ResearchJobState,
    TERMINAL_STATES,
)


class InvalidTransition(Exception):
    """Raised when a state transition is not allowed."""


class MissingClosureEvidence(Exception):
    """Raised when trying to close a job without a LiftResult."""


# Valid transitions: from_state → set of allowed to_states
VALID_TRANSITIONS: dict[ResearchJobState, frozenset[ResearchJobState]] = {
    "intake_open": frozenset({"research_running"}),
    "research_running": frozenset({"research_done_implementation_pending"}),
    "research_done_implementation_pending": frozenset({
        "implemented_verified",
        "parked_verified",
        "rejected_verified",
        "no_action_verified",
    }),
    "implemented_verified": frozenset(),
    "parked_verified": frozenset(),
    "rejected_verified": frozenset(),
    "no_action_verified": frozenset(),
}

# Map from LiftResult outcome to the corresponding terminal state
OUTCOME_TO_STATE: dict[str, ResearchJobState] = {
    "implemented": "implemented_verified",
    "parked": "parked_verified",
    "rejected": "rejected_verified",
    "no_action": "no_action_verified",
}


def transition(job: ResearchJob, to_state: ResearchJobState) -> ResearchJob:
    """Move a job to a new state. Validates the transition.

    Terminal states require a LiftResult on the job.
    Returns a new ResearchJob (immutable-style).
    """
    allowed = VALID_TRANSITIONS.get(job.state, frozenset())
    if to_state not in allowed:
        raise InvalidTransition(
            f"Cannot transition from '{job.state}' to '{to_state}'. "
            f"Allowed: {sorted(allowed) if allowed else 'none (terminal state)'}."
        )

    if to_state in TERMINAL_STATES and job.lift_result is None:
        raise MissingClosureEvidence(
            f"Cannot close job '{job.job_id}' as '{to_state}' without "
            "a LiftResult. Attach closure evidence first."
        )

    return job.model_copy(update={"state": to_state})


def close_job(job: ResearchJob, lift_result: LiftResult) -> ResearchJob:
    """Attach closure evidence and transition to the matching terminal state.

    The job must be in 'research_done_implementation_pending'.
    The LiftResult's outcome determines the terminal state.
    """
    if job.state != "research_done_implementation_pending":
        raise InvalidTransition(
            f"Cannot close job in state '{job.state}'. "
            "Job must be in 'research_done_implementation_pending'."
        )

    target_state = OUTCOME_TO_STATE.get(lift_result.outcome)
    if target_state is None:
        raise ValueError(f"Unknown LiftResult outcome: '{lift_result.outcome}'")

    updated = job.model_copy(update={"lift_result": lift_result})
    return transition(updated, target_state)
