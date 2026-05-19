"""Tests for research pipe — models, state machine, closure, and portable spine.

Covers the three required invariants from IMPLEMENTATION_PLAN.md § PR 6:
  1. Research job cannot close without closure evidence
  2. State machine enforces valid transitions only
  3. Portable spine carries explicit omissions and valid_until

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow imports from 02_build/
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_pipe.models import (  # noqa: E402
    ClaimEvidenceLink,
    EvidenceItem,
    LiftResult,
    ResearchJob,
    ResearchQuestion,
    TERMINAL_STATES,
)
from research_pipe.state_machine import (  # noqa: E402
    InvalidTransition,
    MissingClosureEvidence,
    VALID_TRANSITIONS,
    close_job,
    transition,
)
from research_pipe.closure import (  # noqa: E402
    IncompleteClosureError,
    assert_closure,
    validate_closure,
)
from research_pipe.portable_spine import (  # noqa: E402
    DEFAULT_EXCLUDES,
    PortableSpine,
    generate_spine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job(**kw: object) -> ResearchJob:
    defaults: dict = {"title": "Test research job"}
    defaults.update(kw)
    return ResearchJob(**defaults)


def _lift(**kw: object) -> LiftResult:
    defaults: dict = {
        "outcome": "implemented",
        "summary": "Implemented and verified.",
        "decided_by": "test_actor",
    }
    defaults.update(kw)
    return LiftResult(**defaults)


# ===================================================================
# 1. Models
# ===================================================================


class TestModels:
    def test_research_job_defaults(self) -> None:
        job = _job()
        assert job.state == "intake_open"
        assert job.lift_result is None
        assert job.questions == []
        assert job.evidence == []

    def test_evidence_item_fields(self) -> None:
        ev = EvidenceItem(source="paper.pdf", content="Finding X")
        assert ev.evidence_id
        assert ev.source == "paper.pdf"

    def test_research_question_fields(self) -> None:
        q = ResearchQuestion(text="Does X cause Y?")
        assert q.status == "open"
        assert q.answer == ""

    def test_claim_evidence_link(self) -> None:
        link = ClaimEvidenceLink(
            claim="X causes Y", evidence_id="ev-1", strength=0.8,
        )
        assert link.relationship == "supports"
        assert link.strength == 0.8

    def test_lift_result_fields(self) -> None:
        lr = _lift()
        assert lr.outcome == "implemented"
        assert lr.decided_by == "test_actor"

    def test_terminal_states_are_four(self) -> None:
        assert len(TERMINAL_STATES) == 4
        assert "implemented_verified" in TERMINAL_STATES
        assert "parked_verified" in TERMINAL_STATES
        assert "rejected_verified" in TERMINAL_STATES
        assert "no_action_verified" in TERMINAL_STATES


# ===================================================================
# 2. State machine — valid transitions only
# ===================================================================


class TestStateMachine:
    def test_happy_path_to_implemented(self) -> None:
        job = _job()
        job = transition(job, "research_running")
        assert job.state == "research_running"
        job = transition(job, "research_done_implementation_pending")
        assert job.state == "research_done_implementation_pending"
        job = close_job(job, _lift(outcome="implemented"))
        assert job.state == "implemented_verified"

    def test_happy_path_to_parked(self) -> None:
        job = _job()
        job = transition(job, "research_running")
        job = transition(job, "research_done_implementation_pending")
        job = close_job(job, _lift(outcome="parked", summary="Parked for later."))
        assert job.state == "parked_verified"

    def test_happy_path_to_rejected(self) -> None:
        job = _job()
        job = transition(job, "research_running")
        job = transition(job, "research_done_implementation_pending")
        job = close_job(job, _lift(outcome="rejected", summary="Not viable."))
        assert job.state == "rejected_verified"

    def test_happy_path_to_no_action(self) -> None:
        job = _job()
        job = transition(job, "research_running")
        job = transition(job, "research_done_implementation_pending")
        job = close_job(job, _lift(outcome="no_action", summary="No action needed."))
        assert job.state == "no_action_verified"

    def test_cannot_skip_states(self) -> None:
        job = _job()
        try:
            transition(job, "research_done_implementation_pending")
            assert False, "Should have raised InvalidTransition"
        except InvalidTransition:
            pass

    def test_cannot_go_backwards(self) -> None:
        job = _job()
        job = transition(job, "research_running")
        try:
            transition(job, "intake_open")
            assert False, "Should have raised InvalidTransition"
        except InvalidTransition:
            pass

    def test_terminal_states_have_no_transitions(self) -> None:
        for state in TERMINAL_STATES:
            assert VALID_TRANSITIONS[state] == frozenset()

    def test_cannot_transition_from_terminal(self) -> None:
        job = _job()
        job = transition(job, "research_running")
        job = transition(job, "research_done_implementation_pending")
        job = close_job(job, _lift())
        assert job.state == "implemented_verified"
        try:
            transition(job, "research_running")
            assert False, "Should have raised InvalidTransition"
        except InvalidTransition:
            pass

    def test_cannot_close_without_lift_result(self) -> None:
        job = _job()
        job = transition(job, "research_running")
        job = transition(job, "research_done_implementation_pending")
        try:
            transition(job, "implemented_verified")
            assert False, "Should have raised MissingClosureEvidence"
        except MissingClosureEvidence:
            pass

    def test_close_job_requires_pending_state(self) -> None:
        job = _job()
        try:
            close_job(job, _lift())
            assert False, "Should have raised InvalidTransition"
        except InvalidTransition:
            pass


# ===================================================================
# 3. Closure validation
# ===================================================================


class TestClosure:
    def test_valid_closure(self) -> None:
        job = _job()
        job = transition(job, "research_running")
        job = transition(job, "research_done_implementation_pending")
        job = close_job(job, _lift())
        problems = validate_closure(job)
        assert problems == []

    def test_non_terminal_flagged(self) -> None:
        job = _job()
        problems = validate_closure(job)
        assert any("non-terminal" in p for p in problems)

    def test_missing_lift_result_flagged(self) -> None:
        job = _job(state="implemented_verified")
        problems = validate_closure(job)
        assert any("LiftResult" in p for p in problems)

    def test_empty_summary_flagged(self) -> None:
        job = _job(
            state="implemented_verified",
            lift_result=_lift(summary=""),
        )
        problems = validate_closure(job)
        assert any("empty summary" in p for p in problems)

    def test_missing_attribution_flagged(self) -> None:
        job = _job(
            state="implemented_verified",
            lift_result=_lift(decided_by=""),
        )
        problems = validate_closure(job)
        assert any("decided_by" in p for p in problems)

    def test_assert_closure_raises(self) -> None:
        job = _job()
        try:
            assert_closure(job)
            assert False, "Should have raised IncompleteClosureError"
        except IncompleteClosureError:
            pass

    def test_assert_closure_clean(self) -> None:
        job = _job()
        job = transition(job, "research_running")
        job = transition(job, "research_done_implementation_pending")
        job = close_job(job, _lift())
        assert_closure(job)


# ===================================================================
# 4. Portable spine
# ===================================================================


class TestPortableSpine:
    def test_generate_spine_includes(self) -> None:
        spine = generate_spine(
            problem_id="prob-1",
            task_summary="Research running",
            agent_role_target="devon",
            constraints=["no FalkorDB"],
            allowed_tools=["grep", "git"],
        )
        assert spine.task_summary == "Research running"
        assert "no FalkorDB" in spine.constraints
        assert spine.allowed_tools == ["grep", "git"]
        # Five Rods always appended
        assert "radical_honesty" in spine.constraints

    def test_spine_has_valid_until(self) -> None:
        spine = generate_spine(
            problem_id="prob-2",
            task_summary="test",
            agent_role_target="devon",
        )
        assert spine.valid_until > datetime.now(timezone.utc)

    def test_spine_custom_ttl(self) -> None:
        spine = generate_spine(
            problem_id="prob-3",
            task_summary="test",
            agent_role_target="devon",
            ttl=timedelta(hours=1),
        )
        expected = datetime.now(timezone.utc) + timedelta(hours=1)
        delta = abs((spine.valid_until - expected).total_seconds())
        assert delta < 2

    def test_spine_expiry_detection(self) -> None:
        spine = PortableSpine(
            valid_until=datetime.now(timezone.utc) - timedelta(hours=1),
            problem_id="prob-4",
            task_summary="expired",
            agent_role_target="devon",
        )
        assert spine.is_expired

    def test_spine_not_expired(self) -> None:
        spine = generate_spine(
            problem_id="prob-5",
            task_summary="fresh",
            agent_role_target="devon",
        )
        assert not spine.is_expired

    def test_default_excludes_present(self) -> None:
        spine = generate_spine(
            problem_id="prob-6",
            task_summary="test",
            agent_role_target="devon",
        )
        for excl in DEFAULT_EXCLUDES:
            assert excl in spine.excluded

    def test_extra_excludes_appended(self) -> None:
        spine = generate_spine(
            problem_id="prob-7",
            task_summary="test",
            agent_role_target="devon",
            extra_excludes=["secret_data"],
        )
        assert "secret_data" in spine.excluded
        for excl in DEFAULT_EXCLUDES:
            assert excl in spine.excluded

    def test_excludes_contain_crm_records(self) -> None:
        spine = generate_spine(
            problem_id="prob-8",
            task_summary="test",
            agent_role_target="devon",
        )
        assert "direct_crm_records" in spine.excluded

    def test_excludes_contain_raw_transcript(self) -> None:
        spine = generate_spine(
            problem_id="prob-9",
            task_summary="test",
            agent_role_target="devon",
        )
        assert "raw_transcript" in spine.excluded

    def test_handoff_prompt(self) -> None:
        spine = generate_spine(
            problem_id="prob-10",
            task_summary="test",
            agent_role_target="devon",
            handoff_prompt="Fix the quarantine routing bug.",
        )
        assert spine.handoff_prompt == "Fix the quarantine routing bug."
