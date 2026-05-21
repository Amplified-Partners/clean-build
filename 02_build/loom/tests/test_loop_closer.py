"""LoopCloser tests.

Covers:
  - Confirmed improvement writes MEASURED entry and closes Linear issue
  - Failed proposal triggers rollback through pipe and writes STRUCTURED failure entry
  - Rollbacks are first-class witnessed events (invariant §6.4)
  - Evaluation logic handles various metric shapes

Dana | 2026-05-20 | From Computer's Loom spec §8
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from loom.integrations.linear import LinearClient
from loom.integrations.pipe import PipeClient
from loom.integrations.vellum import VellumClient
from loom.proposals import Proposal
from loom.workflows.loop_closer import evaluate_proposal, run_loop_closer
from vellum.storage import get_store, init_store
from vellum.storage.memory import MemorySheetStore


@pytest_asyncio.fixture(autouse=True)
async def _setup():
    store = await init_store()
    yield
    if isinstance(store, MemorySheetStore):
        store.clear()


def _make_proposal(**overrides) -> Proposal:
    defaults = {
        "title": "Test proposal",
        "rationale": "Testing",
        "intervention": {"action": "test"},
        "baseline_metric": {"total": 100},
        "expected_metric": "tier_distribution",
    }
    defaults.update(overrides)
    return Proposal(**defaults)


class TestEvaluateProposal:
    def test_improvement_confirmed(self) -> None:
        """After metric > before metric → confirmed."""
        p = _make_proposal(baseline_metric={"total": 100})
        result = evaluate_proposal(p, {"total": 100}, {"total": 120})
        assert result["confirmed"] is True

    def test_regression_not_confirmed(self) -> None:
        """After metric < before metric → not confirmed."""
        p = _make_proposal(baseline_metric={"total": 100})
        result = evaluate_proposal(p, {"total": 100}, {"total": 80})
        assert result["confirmed"] is False

    def test_steady_state_confirmed(self) -> None:
        """No change → confirmed (held steady is acceptable)."""
        p = _make_proposal(baseline_metric={"total": 100})
        result = evaluate_proposal(p, {"total": 100}, {"total": 100})
        assert result["confirmed"] is True

    def test_budget_halt_inverted(self) -> None:
        """For budget halt: lower spend = confirmed."""
        p = _make_proposal(
            intervention={"action": "halt_vendor_workflows"},
            baseline_metric={"total": 500},
        )
        # Spend decreased
        result = evaluate_proposal(p, {"total": 500}, {"total": 300})
        assert result["confirmed"] is True

        # Spend increased
        result = evaluate_proposal(p, {"total": 500}, {"total": 600})
        assert result["confirmed"] is False

    def test_incomparable_defaults_safe(self) -> None:
        """Non-numeric metrics → default to not confirmed (safe)."""
        p = _make_proposal(baseline_metric={"status": "ok"})
        result = evaluate_proposal(p, {"status": "ok"}, {"status": "bad"})
        assert result["confirmed"] is False


class TestRunLoopCloser:
    @pytest.mark.asyncio
    async def test_confirmed_writes_measured_entry(self) -> None:
        """Confirmed improvement → MEASURED entry in Vellum."""
        proposal = _make_proposal(baseline_metric={"total": 100})
        vellum = VellumClient()
        pipe = PipeClient()
        linear = LinearClient()

        result = await run_loop_closer(
            proposal, {"total": 120}, vellum, pipe, linear
        )

        assert result["confirmed"] is True

        # Check MEASURED entry in Vellum
        store = get_store()
        sheets = await store.list_sheets("ewan")
        kaizen = [s for s in sheets if s.meta.title == "kaizen-log"]
        assert len(kaizen) == 1
        measured = [
            e for e in kaizen[0].entries
            if e.epistemic_tier == "MEASURED"
        ]
        assert len(measured) == 1
        assert "confirmed improvement" in measured[0].content

    @pytest.mark.asyncio
    async def test_confirmed_closes_linear_issue(self) -> None:
        """Confirmed → Linear issue closed with kaizen-confirmed label."""
        proposal = _make_proposal(baseline_metric={"total": 100})
        vellum = VellumClient()
        pipe = PipeClient()
        linear = LinearClient()

        await run_loop_closer(proposal, {"total": 120}, vellum, pipe, linear)

        closed = linear.get_closed()
        assert len(closed) == 1
        assert closed[0]["label"] == "kaizen-confirmed"

    @pytest.mark.asyncio
    async def test_failed_triggers_rollback(self) -> None:
        """Failed proposal → rollback through pipe (invariant §6.4)."""
        proposal = _make_proposal(baseline_metric={"total": 100})
        vellum = VellumClient()
        pipe = PipeClient()
        linear = LinearClient()

        result = await run_loop_closer(
            proposal, {"total": 80}, vellum, pipe, linear
        )

        assert result["confirmed"] is False

        # Rollback went through pipe
        assert proposal.id in pipe.get_rollbacks()

    @pytest.mark.asyncio
    async def test_failed_writes_structured_entry(self) -> None:
        """Failed proposal → STRUCTURED entry (stays heuristic, not measured)."""
        proposal = _make_proposal(baseline_metric={"total": 100})
        vellum = VellumClient()
        pipe = PipeClient()
        linear = LinearClient()

        await run_loop_closer(proposal, {"total": 50}, vellum, pipe, linear)

        store = get_store()
        sheets = await store.list_sheets("ewan")
        kaizen = [s for s in sheets if s.meta.title == "kaizen-log"]
        assert len(kaizen) == 1
        structured = [
            e for e in kaizen[0].entries
            if "rolled back" in e.content
        ]
        assert len(structured) == 1
        assert structured[0].epistemic_tier == "STRUCTURED"

    @pytest.mark.asyncio
    async def test_failed_closes_linear_with_failed_label(self) -> None:
        """Failed → Linear issue closed with kaizen-failed label."""
        proposal = _make_proposal(baseline_metric={"total": 100})
        vellum = VellumClient()
        pipe = PipeClient()
        linear = LinearClient()

        await run_loop_closer(proposal, {"total": 50}, vellum, pipe, linear)

        closed = linear.get_closed()
        assert len(closed) == 1
        assert closed[0]["label"] == "kaizen-failed"

    @pytest.mark.asyncio
    async def test_rollback_is_witnessed(self) -> None:
        """Invariant §6.4: Failed proposals are witnessed, not silently deleted."""
        proposal = _make_proposal(baseline_metric={"total": 100})
        vellum = VellumClient()
        pipe = PipeClient()
        linear = LinearClient()

        await run_loop_closer(proposal, {"total": 50}, vellum, pipe, linear)

        # The rollback must produce at least one Vellum entry
        store = get_store()
        sheets = await store.list_sheets("ewan")
        kaizen = [s for s in sheets if s.meta.title == "kaizen-log"]
        assert len(kaizen) == 1
        assert len(kaizen[0].entries) >= 1
        # The entry must contain the proposal ID for traceability
        last = kaizen[0].entries[-1]
        assert proposal.id in last.metadata.get("proposal_id", "")

    @pytest.mark.asyncio
    async def test_only_loop_closer_promotes_to_measured(self) -> None:
        """Invariant §6.3: Only LoopCloser may write MEASURED entries.

        Confirmed proposals get MEASURED. Failed proposals stay STRUCTURED.
        This is the tier promotion gate.
        """
        # Confirmed → MEASURED
        p1 = _make_proposal(baseline_metric={"total": 100})
        vellum1 = VellumClient()
        pipe1 = PipeClient()
        linear1 = LinearClient()
        await run_loop_closer(p1, {"total": 120}, vellum1, pipe1, linear1)

        # Failed → STRUCTURED
        p2 = _make_proposal(baseline_metric={"total": 100})
        vellum2 = VellumClient()
        pipe2 = PipeClient()
        linear2 = LinearClient()
        await run_loop_closer(p2, {"total": 50}, vellum2, pipe2, linear2)

        # Check p1's entries
        store = get_store()
        sheets = await store.list_sheets("ewan")
        kaizen_sheets = [s for s in sheets if s.meta.title == "kaizen-log"]

        measured_entries = []
        structured_entries = []
        for ks in kaizen_sheets:
            for e in ks.entries:
                if e.epistemic_tier == "MEASURED":
                    measured_entries.append(e)
                elif "rolled back" in e.content or "confirmed" in e.content:
                    structured_entries.append(e)

        assert len(measured_entries) >= 1  # Confirmed gets MEASURED
        # All measured entries are from loop_closer
        for e in measured_entries:
            assert e.author == "loom.loop_closer"
