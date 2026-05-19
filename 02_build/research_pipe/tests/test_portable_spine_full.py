"""Tests for portable spine — full Amplified Weight shape.

Covers:
  1. RawRecord, KnowledgeUnit, LiftCandidate model construction
  2. PortableSpine with SpineContext, minimum_tier_required, constraints
  3. AgentWriteback — the learning loop
  4. generate_spine defaults Five Rods as constraints
  5. Spine expiry mechanism
  6. LiftResult python shape extraction fields
  7. ResearchJob autonomous builder directive fields

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from epistemic_core.tiers import EpistemicTier  # noqa: E402
from research_pipe.portable_spine import (  # noqa: E402
    AgentWriteback,
    DEFAULT_EXCLUDES,
    KnowledgeUnit,
    LiftCandidate,
    Modality,
    PermittedUse,
    PortableSpine,
    RawRecord,
    SpineContext,
    generate_spine,
)
from research_pipe.models import (  # noqa: E402
    LiftResult,
    ResearchJob,
)


# ===================================================================
# 1. RawRecord
# ===================================================================


class TestRawRecord:
    def test_construction(self) -> None:
        r = RawRecord(
            source_type=Modality.VOICE,
            source_ref="transcript-001",
            content="Hello world",
            content_hash=hashlib.sha256(b"Hello world").hexdigest(),
            actor="ewan",
        )
        assert r.source_type == Modality.VOICE
        assert r.actor == "ewan"
        assert r.boundary_policy == "anonymise_where_feasible"
        assert r.record_id  # auto-generated

    def test_all_modalities(self) -> None:
        for mod in Modality:
            r = RawRecord(
                source_type=mod,
                source_ref="test",
                content="x",
                content_hash="abc",
                actor="test",
            )
            assert r.source_type == mod


# ===================================================================
# 2. KnowledgeUnit
# ===================================================================


class TestKnowledgeUnit:
    def test_construction(self) -> None:
        ku = KnowledgeUnit(
            packet_type="opinion",
            content="AI is a pudding",
            epistemic_tier=EpistemicTier.INTUITED,
            source_record_ids=["rec-1", "rec-2"],
            permitted_use=[PermittedUse.DOCTRINE_SEED],
        )
        assert ku.epistemic_tier == EpistemicTier.INTUITED
        assert ku.permitted_use == [PermittedUse.DOCTRINE_SEED]
        assert ku.not_for == []
        assert ku.unit_id

    def test_attribution_chain(self) -> None:
        ku = KnowledgeUnit(
            packet_type="method",
            content="Pudding technique",
            epistemic_tier=EpistemicTier.STRUCTURED,
            source_record_ids=["rec-1"],
            attribution_originated_by=["ewan"],
            attribution_crystallised_by=["cassian", "devon"],
        )
        assert "ewan" in ku.attribution_originated_by
        assert len(ku.attribution_crystallised_by) == 2


# ===================================================================
# 3. LiftCandidate
# ===================================================================


class TestLiftCandidate:
    def test_construction(self) -> None:
        lc = LiftCandidate(
            knowledge_unit_id="ku-1",
            candidate_type="method_hypothesis",
            current_tier=EpistemicTier.INTUITED,
            target_claim_or_gap="Need agent execution shape",
            business_value_score=4,
            agent_reuse_score=3,
            risk_if_wrong_score=2,
            recommended_route="research_pipe",
        )
        assert lc.business_value_score == 4
        assert lc.current_tier == EpistemicTier.INTUITED
        assert lc.candidate_id


# ===================================================================
# 4. PortableSpine + SpineContext
# ===================================================================


class TestPortableSpine:
    def test_construction_with_context(self) -> None:
        ctx = SpineContext(
            brain_facts=[{"fact": "Vellum is permanent"}],
            github_state={"repo": "clean-build", "branch": "main"},
            decisions=[{"decision": "sample floor = 30"}],
        )
        spine = PortableSpine(
            problem_id="prob-1",
            task_summary="Fix quarantine routing",
            agent_role_target="devon",
            context=ctx,
        )
        assert spine.minimum_tier_required == EpistemicTier.STRUCTURED
        assert len(spine.context.brain_facts) == 1
        assert spine.context.github_state["repo"] == "clean-build"
        assert spine.spine_id

    def test_minimum_tier(self) -> None:
        spine = PortableSpine(
            problem_id="prob-2",
            task_summary="Deploy to Beast",
            agent_role_target="devon",
            minimum_tier_required=EpistemicTier.MEASURED,
        )
        assert spine.minimum_tier_required == EpistemicTier.MEASURED

    def test_expiry(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        spine = PortableSpine(
            problem_id="prob-3",
            task_summary="Expired task",
            agent_role_target="devon",
            valid_until=past,
        )
        assert spine.is_expired is True

    def test_not_expired(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(hours=24)
        spine = PortableSpine(
            problem_id="prob-4",
            task_summary="Active task",
            agent_role_target="devon",
            valid_until=future,
        )
        assert spine.is_expired is False

    def test_no_expiry(self) -> None:
        spine = PortableSpine(
            problem_id="prob-5",
            task_summary="No TTL",
            agent_role_target="devon",
        )
        assert spine.is_expired is False

    def test_allowed_and_disallowed_tools(self) -> None:
        spine = PortableSpine(
            problem_id="prob-6",
            task_summary="Restricted task",
            agent_role_target="devon",
            allowed_tools=["git", "grep"],
            disallowed_tools=["ssh"],
        )
        assert "git" in spine.allowed_tools
        assert "ssh" in spine.disallowed_tools


# ===================================================================
# 5. generate_spine
# ===================================================================


class TestGenerateSpine:
    def test_defaults_five_rods(self) -> None:
        spine = generate_spine(
            problem_id="prob-gen",
            task_summary="Test generation",
            agent_role_target="devon",
        )
        assert "radical_honesty" in spine.constraints
        assert "radical_transparency" in spine.constraints
        assert "radical_attribution" in spine.constraints
        assert "win_win" in spine.constraints
        assert "idea_meritocracy" in spine.constraints

    def test_default_excludes(self) -> None:
        spine = generate_spine(
            problem_id="prob-gen",
            task_summary="Test generation",
            agent_role_target="devon",
        )
        for excl in DEFAULT_EXCLUDES:
            assert excl in spine.excluded

    def test_extra_excludes(self) -> None:
        spine = generate_spine(
            problem_id="prob-gen",
            task_summary="Test generation",
            agent_role_target="devon",
            extra_excludes=["pii_data"],
        )
        assert "pii_data" in spine.excluded
        assert "raw_transcript" in spine.excluded

    def test_ttl(self) -> None:
        spine = generate_spine(
            problem_id="prob-gen",
            task_summary="Short TTL",
            agent_role_target="devon",
            ttl=timedelta(hours=1),
        )
        assert spine.valid_until is not None
        assert spine.is_expired is False

    def test_custom_constraints_plus_five_rods(self) -> None:
        spine = generate_spine(
            problem_id="prob-gen",
            task_summary="Extra constraints",
            agent_role_target="devon",
            constraints=["no_production_mutations"],
        )
        assert "no_production_mutations" in spine.constraints
        assert "radical_honesty" in spine.constraints

    def test_handoff_prompt(self) -> None:
        spine = generate_spine(
            problem_id="prob-gen",
            task_summary="With handoff",
            agent_role_target="devon",
            handoff_prompt="Fix the quarantine routing bug.",
        )
        assert spine.handoff_prompt == "Fix the quarantine routing bug."


# ===================================================================
# 6. AgentWriteback
# ===================================================================


class TestAgentWriteback:
    def test_construction(self) -> None:
        wb = AgentWriteback(
            spine_id="spine-1",
            agent_id="devon-d493",
            status="success",
            what_changed=["Fixed quarantine routing"],
            decisions_made=["Used verdict over route"],
            reusable_patterns=["verdict-wins-route pattern"],
            mistakes_avoided=["Relying on route field only"],
            spine_effectiveness_note="Spine was well-scoped, no missing context.",
        )
        assert wb.status == "success"
        assert len(wb.what_changed) == 1
        assert len(wb.reusable_patterns) == 1
        assert wb.writeback_id

    def test_failed_writeback(self) -> None:
        wb = AgentWriteback(
            spine_id="spine-2",
            agent_id="devon-d493",
            status="failed",
            what_changed=[],
            decisions_made=[],
            spine_effectiveness_note="Missing API key for Brevo.",
        )
        assert wb.status == "failed"
        assert wb.what_changed == []


# ===================================================================
# 7. LiftResult — python shape extraction
# ===================================================================


class TestLiftResultShapeExtraction:
    def test_proposed_python_shapes(self) -> None:
        lr = LiftResult(
            outcome="implemented",
            summary="Extracted agent execution shapes",
            proposed_python_shapes=[
                "class CloudAgent(BaseModel): name: str",
                "class AgentLifecycle(BaseModel): steps: list[str]",
            ],
            business_wireframe_gaps_filled=[
                "Agent Operations bald spot",
            ],
        )
        assert len(lr.proposed_python_shapes) == 2
        assert "CloudAgent" in lr.proposed_python_shapes[0]
        assert len(lr.business_wireframe_gaps_filled) == 1

    def test_default_empty(self) -> None:
        lr = LiftResult(
            outcome="no_action",
            summary="No shapes needed",
        )
        assert lr.proposed_python_shapes == []
        assert lr.business_wireframe_gaps_filled == []


# ===================================================================
# 8. ResearchJob — autonomous builder directive
# ===================================================================


class TestResearchJobBuilderDirective:
    def test_defaults_off(self) -> None:
        job = ResearchJob(title="Basic job")
        assert job.requires_python_shape_extraction is False
        assert job.target_python_domain == ""

    def test_builder_enabled(self) -> None:
        job = ResearchJob(
            title="Shape extraction job",
            requires_python_shape_extraction=True,
            target_python_domain="marketing_engine",
        )
        assert job.requires_python_shape_extraction is True
        assert job.target_python_domain == "marketing_engine"
