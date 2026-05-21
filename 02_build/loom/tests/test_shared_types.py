"""Shared types tests — Finding and Proposal dataclasses.

Dana | 2026-05-20
"""

from __future__ import annotations

import pytest

from loom.findings import Finding
from loom.proposals import Proposal


class TestFinding:
    def test_finding_defaults_to_structured(self) -> None:
        """Findings are always STRUCTURED — heuristic, not measured."""
        f = Finding(kind="test")
        assert f.tier == "STRUCTURED"

    def test_finding_defaults_to_info(self) -> None:
        f = Finding(kind="test")
        assert f.severity == "info"

    def test_to_vellum_entry(self) -> None:
        f = Finding(
            kind="triangulation_drop",
            severity="warning",
            source_workflow="loom.brain_health",
            evidence={"rate": 0.5},
        )
        entry = f.to_vellum_entry()
        assert entry["entry_type"] == "metric"
        assert entry["author"] == "loom.brain_health"
        assert entry["epistemic_tier"] == "STRUCTURED"
        assert "triangulation_drop" in entry["content"]
        assert entry["metadata"]["finding_id"] == f.id
        assert entry["metadata"]["evidence"] == {"rate": 0.5}

    def test_finding_has_unique_id(self) -> None:
        f1 = Finding(kind="a")
        f2 = Finding(kind="b")
        assert f1.id != f2.id

    def test_finding_preserves_related_entities(self) -> None:
        f = Finding(
            kind="agent_silent",
            related_entity_ids=["devin", "cove"],
        )
        entry = f.to_vellum_entry()
        assert entry["metadata"]["related"] == ["devin", "cove"]


class TestProposal:
    def test_proposal_defaults_to_structured(self) -> None:
        """Proposals are always STRUCTURED — heuristic interventions."""
        p = Proposal(title="Test")
        assert p.tier == "STRUCTURED"

    def test_to_pipe_submission(self) -> None:
        p = Proposal(
            title="Lower threshold",
            intervention={"action": "lower_corroboration"},
            reversible=True,
            observation_window_hours=168,
        )
        sub = p.to_pipe_submission()
        assert sub["kind"] == "meta_change"
        assert sub["attributed_to"] == "loom.kaizen_generator"
        assert sub["tier"] == "STRUCTURED"
        assert sub["rollback_plan"]["reversible"] is True
        assert sub["rollback_plan"]["window_hours"] == 168

    def test_to_vellum_entry(self) -> None:
        p = Proposal(title="Test proposal", rationale="Testing")
        entry = p.to_vellum_entry()
        assert entry["epistemic_tier"] == "STRUCTURED"
        assert entry["author"] == "loom.kaizen_generator"
        assert "Test proposal" in entry["content"]

    def test_default_observation_window(self) -> None:
        p = Proposal(title="Test")
        assert p.observation_window_hours == 168  # 7 days
