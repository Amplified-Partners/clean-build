"""§3.4 — Council SPLIT does not launder a non-decision into a verdict.

Proves that when the Council of Three produces a SPLIT verdict,
no synthesised council_answer is written. Instead, a decision entry
with "escalated_to_human" is stored with epistemic_tier=INTUITED.

Also validates:
- UNANIMOUS → council_answer with STRUCTURED tier
- MAJORITY → council_answer with STRUCTURED tier + dissent_recorded

Dana | 2026-05-20 | P1 test §3.4
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio

from vellum.council.context import CouncilContext
from vellum.council.engine import MemberResponse, Verdict
from vellum.models.sheet import SheetMeta
from vellum.routes.council import CouncilRequest, submit_council_question
from vellum.storage import init_store, get_store
from vellum.storage.memory import MemorySheetStore


@pytest_asyncio.fixture(autouse=True)
async def _setup_store():
    store = await init_store()
    yield
    if isinstance(store, MemorySheetStore):
        store.clear()


def _mock_call_factory(recommendations: list[str]):
    """Create a mock _call_model that returns fixed recommendations."""
    idx = 0

    async def mock_call(member, prompt, system_prompt=""):
        nonlocal idx
        rec = recommendations[idx % len(recommendations)]
        idx += 1
        return MemberResponse(
            label=member.label,
            model_id=member.model_id,
            recommendation=rec,
            raw_response=rec,
            latency_ms=100.0,
        )

    return mock_call


class TestCouncilSplitNoVerdict:
    """SPLIT verdict must NOT produce a synthesised council_answer."""

    @pytest.mark.asyncio
    async def test_split_produces_decision_not_council_answer(self) -> None:
        store = get_store()
        meta = SheetMeta(id="split-test", title="Split Test", mode="council")
        await store.create_sheet(meta)

        # Three completely different recommendations → SPLIT
        mock = _mock_call_factory([
            "Absolutely proceed immediately with deployment",
            "Wait for quarterly review cycle before any action",
            "Gather customer feedback first before deciding",
        ])

        with patch("vellum.council.engine._call_model", side_effect=mock):
            resp = await submit_council_question("split-test", CouncilRequest(
                question="Should we deploy Vellum to Beast today?",
                author="ewan",
            ))

        assert resp.verdict == "split"
        assert resp.escalate is True

        # Check what was written to the sheet
        sheet = await store.get_sheet("split-test")
        assert sheet is not None

        # The LAST entry is the verdict entry
        verdict_entry = sheet.entries[-1]

        # §3.4: SPLIT must NOT write a council_answer verdict
        assert verdict_entry.entry_type == "decision"
        assert verdict_entry.epistemic_tier == "INTUITED"
        assert "escalated" in verdict_entry.content.lower()
        assert verdict_entry.metadata.get("requires_human_followup") is True
        assert verdict_entry.metadata.get("verdict") == "split"

    @pytest.mark.asyncio
    async def test_unanimous_produces_structured_council_answer(self) -> None:
        store = get_store()
        meta = SheetMeta(id="unanimous-test", title="Unanimous Test", mode="council")
        await store.create_sheet(meta)

        # All agree → UNANIMOUS
        mock = _mock_call_factory([
            "Deploy to production. The tests pass and the architecture is sound.",
        ])

        with patch("vellum.council.engine._call_model", side_effect=mock):
            resp = await submit_council_question("unanimous-test", CouncilRequest(
                question="Should we deploy Vellum to Beast today?",
                author="ewan",
            ))

        assert resp.verdict == "unanimous"

        sheet = await store.get_sheet("unanimous-test")
        verdict_entry = sheet.entries[-1]

        assert verdict_entry.entry_type == "council_answer"
        assert verdict_entry.epistemic_tier == "STRUCTURED"
        assert "dissent_recorded" not in verdict_entry.metadata

    @pytest.mark.asyncio
    async def test_majority_produces_structured_with_dissent(self) -> None:
        store = get_store()
        meta = SheetMeta(id="majority-test", title="Majority Test", mode="council")
        await store.create_sheet(meta)

        # Two agree (A, B), one dissents (C) → MAJORITY
        # Uses member label so the pattern holds across debate rounds
        async def mock_call(member, prompt, system_prompt=""):
            if member.label == "C":
                rec = "Wait until next week for more testing coverage"
            else:
                rec = "Deploy today it is ready and the tests all pass"
            return MemberResponse(
                label=member.label,
                model_id=member.model_id,
                recommendation=rec,
                raw_response=rec,
                latency_ms=100.0,
            )

        with patch("vellum.council.engine._call_model", side_effect=mock_call):
            resp = await submit_council_question("majority-test", CouncilRequest(
                question="Should we deploy Vellum to Beast today?",
                author="ewan",
            ))

        # After debate, MAJORITY can upgrade to UNANIMOUS if members converge.
        # Either way, the verdict entry should be STRUCTURED.
        assert resp.verdict in ("majority", "unanimous")

        sheet = await store.get_sheet("majority-test")
        verdict_entry = sheet.entries[-1]

        assert verdict_entry.entry_type == "council_answer"
        assert verdict_entry.epistemic_tier == "STRUCTURED"
        # dissent_recorded only present for majority verdicts
        if resp.verdict == "majority":
            assert verdict_entry.metadata.get("dissent_recorded") is True
