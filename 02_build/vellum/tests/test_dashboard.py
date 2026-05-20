"""Dashboard API tests — Mission Control integration.

Covers:
  - Governance snapshot with mixed data
  - Conversation listing
  - Agent roster
  - System health (chain integrity, tier compliance)
  - Empty state handling

Dana | 2026-05-20 | Dashboard tests
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from vellum.models.entry import SheetEntry
from vellum.models.participant import Participant
from vellum.models.sheet import SheetMeta
from vellum.routes.correspondence import (
    CreateConversationRequest,
    SendMessageRequest,
    _add_participant,
    clear_participants,
    create_conversation,
    send_message,
)
from vellum.routes.dashboard import (
    agent_roster,
    governance_snapshot,
    list_conversations,
    system_health,
)
from vellum.storage import get_store, init_store
from vellum.storage.memory import MemorySheetStore


@pytest_asyncio.fixture(autouse=True)
async def _setup():
    store = await init_store()
    yield
    clear_participants()
    if isinstance(store, MemorySheetStore):
        store.clear()


async def _seed_mixed_data():
    """Create a mix of briefs, conversations, and decisions."""
    store = get_store()

    # Brief with some entries
    brief_meta = SheetMeta(title="Morning Brief", mode="brief", created_by="vellum-generator")
    await store.create_sheet(brief_meta)
    prev = ""
    for author, content, etype, tier in [
        ("antigravity", "Morning brief summary", "brief_summary", "STRUCTURED"),
        ("ewan", "Looks good", "human_comment", "INTUITED"),
        ("antigravity", "Approved for today", "decision", "STRUCTURED"),
    ]:
        e = SheetEntry(
            sheet_id=brief_meta.id, author=author, content=content,
            prev_hash=prev, entry_type=etype, epistemic_tier=tier,
        )
        await store.append_entry(brief_meta.id, e)
        prev = e.entry_hash

    # Correspondence conversation
    conv = await create_conversation(CreateConversationRequest(
        title="Ewan + Devon", created_by="ewan", creator_type="human",
        initial_participants=["devon-9892"],
    ))
    await send_message(conv.sheet_id, SendMessageRequest(
        content="How's the build?", author="ewan",
    ))

    return brief_meta.id, conv.sheet_id


# ---------------------------------------------------------------------------
# Governance snapshot
# ---------------------------------------------------------------------------


class TestGovernanceSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_with_data(self) -> None:
        brief_id, conv_id = await _seed_mixed_data()
        snap = await governance_snapshot()

        assert snap["tenant_id"] == "ewan"
        assert snap["summary"]["total_sheets"] == 2
        assert snap["summary"]["total_entries"] == 4  # 3 brief + 1 conversation
        assert snap["summary"]["active_conversations"] == 1

    @pytest.mark.asyncio
    async def test_snapshot_empty_state(self) -> None:
        snap = await governance_snapshot()
        assert snap["summary"]["total_sheets"] == 0
        assert snap["summary"]["total_entries"] == 0
        assert snap["conversations"] == []
        assert snap["recent_decisions"] == []

    @pytest.mark.asyncio
    async def test_snapshot_includes_decisions(self) -> None:
        await _seed_mixed_data()
        snap = await governance_snapshot()
        assert len(snap["recent_decisions"]) == 1
        assert snap["recent_decisions"][0]["entry_type"] == "decision"

    @pytest.mark.asyncio
    async def test_snapshot_tier_distribution(self) -> None:
        await _seed_mixed_data()
        snap = await governance_snapshot()
        tiers = snap["tier_distribution"]
        assert "INTUITED" in tiers
        assert "STRUCTURED" in tiers

    @pytest.mark.asyncio
    async def test_snapshot_agents_listed(self) -> None:
        await _seed_mixed_data()
        snap = await governance_snapshot()
        agent_names = {a["identity"] for a in snap["agents"]}
        assert "ewan" in agent_names
        assert "antigravity" in agent_names


# ---------------------------------------------------------------------------
# Conversation listing
# ---------------------------------------------------------------------------


class TestConversationListing:
    @pytest.mark.asyncio
    async def test_list_conversations(self) -> None:
        _, conv_id = await _seed_mixed_data()
        resp = await list_conversations()
        assert resp["count"] == 1
        assert resp["conversations"][0]["sheet_id"] == conv_id

    @pytest.mark.asyncio
    async def test_list_conversations_includes_participants(self) -> None:
        _, conv_id = await _seed_mixed_data()
        resp = await list_conversations()
        conv = resp["conversations"][0]
        identities = {p["identity"] for p in conv["participants"]}
        assert "ewan" in identities


# ---------------------------------------------------------------------------
# Agent roster
# ---------------------------------------------------------------------------


class TestAgentRoster:
    @pytest.mark.asyncio
    async def test_agent_roster(self) -> None:
        await _seed_mixed_data()
        resp = await agent_roster()
        assert resp["count"] >= 2
        # Most active agent should be first
        assert resp["agents"][0]["entries"] >= resp["agents"][-1]["entries"]

    @pytest.mark.asyncio
    async def test_agent_tier_breakdown(self) -> None:
        await _seed_mixed_data()
        resp = await agent_roster()
        for agent in resp["agents"]:
            assert "tier_breakdown" in agent


# ---------------------------------------------------------------------------
# System health
# ---------------------------------------------------------------------------


class TestSystemHealth:
    @pytest.mark.asyncio
    async def test_healthy_state(self) -> None:
        await _seed_mixed_data()
        resp = await system_health()
        assert resp["status"] == "healthy"
        assert resp["chain_integrity"]["invalid"] == 0
        assert resp["chain_integrity"]["valid"] >= 1

    @pytest.mark.asyncio
    async def test_empty_state_is_healthy(self) -> None:
        resp = await system_health()
        assert resp["status"] == "healthy"
        assert resp["activity"]["total_entries"] == 0

    @pytest.mark.asyncio
    async def test_active_agents_tracked(self) -> None:
        await _seed_mixed_data()
        resp = await system_health()
        assert resp["activity"]["active_agents_24h"] >= 2
