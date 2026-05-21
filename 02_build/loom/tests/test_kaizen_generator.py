"""KaizenProposalGenerator tests.

Covers:
  - Each rule in the rule book produces the correct proposal
  - Novel finding (no rule) escalates to Council
  - Proposals go through pipe (never Brain directly)
  - All proposals are STRUCTURED tier
  - Linear issues opened for each proposal
  - Run-summary always written

Dana | 2026-05-20 | From Computer's Loom spec §8
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from loom.findings import Finding
from loom.integrations.linear import LinearClient
from loom.integrations.pipe import PipeClient
from loom.integrations.vellum import VellumClient
from loom.workflows.kaizen_generator import (
    RULE_BOOK,
    propose_for_finding,
    run_kaizen_generator,
)
from vellum.storage import get_store, init_store
from vellum.storage.memory import MemorySheetStore


@pytest_asyncio.fixture(autouse=True)
async def _setup():
    store = await init_store()
    yield
    if isinstance(store, MemorySheetStore):
        store.clear()


class TestProposeForFinding:
    def test_each_rule_produces_proposal(self) -> None:
        """Every known finding kind produces a proposal."""
        for kind in RULE_BOOK:
            f = Finding(kind=kind, source_workflow="test")
            p = propose_for_finding(f)
            assert p is not None, f"No proposal for finding kind: {kind}"
            assert p.tier == "STRUCTURED"
            assert f.id in p.evidence_finding_ids

    def test_unknown_kind_returns_none(self) -> None:
        """Novel findings (no rule) return None for Council escalation."""
        f = Finding(kind="totally_new_thing", source_workflow="test")
        p = propose_for_finding(f)
        assert p is None

    def test_triangulation_drop_proposal(self) -> None:
        f = Finding(
            kind="triangulation_drop",
            source_workflow="loom.brain_health",
            evidence={"rate": 0.5},
        )
        p = propose_for_finding(f)
        assert p is not None
        assert "corroboration" in p.title.lower()
        assert p.intervention["action"] == "lower_corroboration_threshold"
        assert p.observation_window_hours == 168

    def test_agent_silent_no_auto_intervention(self) -> None:
        """Agent silence → human review, NOT automatic intervention."""
        f = Finding(kind="agent_silent", source_workflow="loom.agent_watcher")
        p = propose_for_finding(f)
        assert p is not None
        assert p.intervention["auto_intervene"] is False

    def test_budget_critical_halts_workflows(self) -> None:
        f = Finding(kind="budget_critical", source_workflow="loom.budget_guard")
        p = propose_for_finding(f)
        assert p is not None
        assert p.intervention["action"] == "halt_vendor_workflows"

    def test_all_proposals_are_structured(self) -> None:
        """Invariant §6.3: Proposals are tier-capped at STRUCTURED."""
        for kind in RULE_BOOK:
            f = Finding(kind=kind, source_workflow="test")
            p = propose_for_finding(f)
            assert p.tier == "STRUCTURED", (
                f"Proposal for {kind} has tier={p.tier}"
            )


class TestRunKaizenGenerator:
    @pytest.mark.asyncio
    async def test_proposals_submitted_through_pipe(self) -> None:
        """Every proposal must go through the pipe."""
        findings = [
            Finding(kind="triangulation_drop", source_workflow="loom.brain_health"),
            Finding(kind="budget_warning", source_workflow="loom.budget_guard"),
        ]
        vellum = VellumClient()
        pipe = PipeClient()
        linear = LinearClient()

        proposals = await run_kaizen_generator(findings, vellum, pipe, linear)

        assert len(proposals) == 2
        assert len(pipe.get_submissions()) == 2
        for sub in pipe.get_submissions():
            assert sub["submission"]["kind"] == "meta_change"
            assert sub["witness_id"]

    @pytest.mark.asyncio
    async def test_linear_issues_opened(self) -> None:
        """Each proposal gets a Linear issue."""
        findings = [Finding(kind="agent_silent", source_workflow="test")]
        vellum = VellumClient()
        pipe = PipeClient()
        linear = LinearClient()

        await run_kaizen_generator(findings, vellum, pipe, linear)

        issues = linear.get_issues()
        assert len(issues) == 1
        assert issues[0]["label"] == "kaizen-proposal"
        assert "vellum://" in issues[0]["body"]

    @pytest.mark.asyncio
    async def test_novel_finding_escalated(self) -> None:
        """Findings without rules get escalated to Council."""
        findings = [Finding(kind="unknown_type", source_workflow="test")]
        vellum = VellumClient()
        pipe = PipeClient()
        linear = LinearClient()

        proposals = await run_kaizen_generator(findings, vellum, pipe, linear)

        assert len(proposals) == 0
        assert len(pipe.get_submissions()) == 0

        # Check escalation was witnessed
        store = get_store()
        sheets = await store.list_sheets("ewan")
        kaizen = [s for s in sheets if s.meta.title == "kaizen-log"]
        assert len(kaizen) == 1
        escalation = [
            e for e in kaizen[0].entries
            if "escalating to Council" in e.content
        ]
        assert len(escalation) == 1

    @pytest.mark.asyncio
    async def test_run_summary_always_written(self) -> None:
        """Generator must always write a run-summary."""
        vellum = VellumClient()
        pipe = PipeClient()
        linear = LinearClient()

        await run_kaizen_generator([], vellum, pipe, linear)

        store = get_store()
        sheets = await store.list_sheets("ewan")
        kaizen = [s for s in sheets if s.meta.title == "kaizen-log"]
        assert len(kaizen) == 1
        last = kaizen[0].entries[-1]
        assert "generated 0 proposals" in last.content

    @pytest.mark.asyncio
    async def test_mixed_known_and_novel_findings(self) -> None:
        """Mix of known and novel findings processed correctly."""
        findings = [
            Finding(kind="triangulation_drop", source_workflow="test"),
            Finding(kind="never_seen_before", source_workflow="test"),
            Finding(kind="budget_critical", source_workflow="test"),
        ]
        vellum = VellumClient()
        pipe = PipeClient()
        linear = LinearClient()

        proposals = await run_kaizen_generator(findings, vellum, pipe, linear)

        assert len(proposals) == 2  # triangulation + budget
        assert len(pipe.get_submissions()) == 2
        assert len(linear.get_issues()) == 2
