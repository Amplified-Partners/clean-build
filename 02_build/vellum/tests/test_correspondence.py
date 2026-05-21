"""Correspondence mode — tests for bidirectional conversation on Vellum.

Covers:
  - Conversation creation with participants
  - Human ↔ Agent messaging with hash chain integrity
  - Agent ↔ Agent (model-to-model) under strict epistemic rules
  - Epistemic tier ceiling enforcement (min-rule)
  - Observer cannot send messages
  - Non-participant rejected
  - Message listing and participant management

Dana | 2026-05-20 | Correspondence mode tests
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from vellum.canvas.hash_chain import HashChain
from vellum.models.participant import Participant, tier_min, TIER_CEILING
from vellum.routes.correspondence import (
    AddParticipantRequest,
    CreateConversationRequest,
    SendMessageRequest,
    add_participant,
    clear_participants,
    create_conversation,
    list_messages,
    list_participants,
    send_message,
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


# ---------------------------------------------------------------------------
# Participant model
# ---------------------------------------------------------------------------


class TestParticipantModel:
    def test_human_ceiling_is_intuited(self) -> None:
        p = Participant(
            sheet_id="s1", identity="ewan", participant_type="human",
            max_tier="STRUCTURED",
        )
        # Ceiling clamps STRUCTURED → INTUITED for humans
        assert p.max_tier == "INTUITED"

    def test_agent_ceiling_is_structured(self) -> None:
        p = Participant(
            sheet_id="s1", identity="antigravity", participant_type="agent",
            max_tier="MEASURED",
        )
        assert p.max_tier == "STRUCTURED"

    def test_model_ceiling_is_structured(self) -> None:
        p = Participant(
            sheet_id="s1", identity="gpt-5.5", participant_type="model",
        )
        assert p.max_tier == "STRUCTURED"

    def test_tier_min_function(self) -> None:
        assert tier_min("INTUITED", "STRUCTURED") == "INTUITED"
        assert tier_min("STRUCTURED", "MEASURED") == "STRUCTURED"
        assert tier_min("MEASURED", "MEASURED") == "MEASURED"
        assert tier_min("PROVEN", "INTUITED") == "INTUITED"

    def test_display_name_defaults_to_identity(self) -> None:
        p = Participant(sheet_id="s1", identity="devon-9892")
        assert p.display_name == "devon-9892"


# ---------------------------------------------------------------------------
# Conversation creation
# ---------------------------------------------------------------------------


class TestCreateConversation:
    @pytest.mark.asyncio
    async def test_create_basic_conversation(self) -> None:
        resp = await create_conversation(CreateConversationRequest(
            title="Ewan + Antigravity",
            created_by="ewan",
            creator_type="human",
        ))
        assert resp.title == "Ewan + Antigravity"
        assert "ewan" in resp.participants
        assert resp.sheet_id

    @pytest.mark.asyncio
    async def test_create_with_initial_participants(self) -> None:
        resp = await create_conversation(CreateConversationRequest(
            title="Team chat",
            created_by="ewan",
            creator_type="human",
            initial_participants=["antigravity", "devon-9892"],
        ))
        assert len(resp.participants) == 3
        assert "antigravity" in resp.participants
        assert "devon-9892" in resp.participants

    @pytest.mark.asyncio
    async def test_sheet_is_correspondence_mode(self) -> None:
        resp = await create_conversation(CreateConversationRequest(
            title="Test",
            created_by="ewan",
        ))
        store = get_store()
        sheet = await store.get_sheet(resp.sheet_id)
        assert sheet is not None
        assert sheet.meta.mode == "correspondence"


# ---------------------------------------------------------------------------
# Sending messages
# ---------------------------------------------------------------------------


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_human_sends_message(self) -> None:
        conv = await create_conversation(CreateConversationRequest(
            title="Test", created_by="ewan", creator_type="human",
        ))
        resp = await send_message(conv.sheet_id, SendMessageRequest(
            content="Morning, what's the plan today?",
            author="ewan",
        ))
        assert resp.author == "ewan"
        assert resp.effective_tier == "INTUITED"  # human ceiling
        assert resp.entry_id

    @pytest.mark.asyncio
    async def test_agent_sends_message(self) -> None:
        conv = await create_conversation(CreateConversationRequest(
            title="Test", created_by="ewan", creator_type="human",
        ))
        # Add agent explicitly (initial_participants inherit creator's type)
        await add_participant(conv.sheet_id, AddParticipantRequest(
            identity="antigravity", participant_type="agent", role="participant",
        ))
        resp = await send_message(conv.sheet_id, SendMessageRequest(
            content="Here's the morning brief summary.",
            author="antigravity",
            epistemic_tier="STRUCTURED",
        ))
        assert resp.effective_tier == "STRUCTURED"

    @pytest.mark.asyncio
    async def test_messages_are_hash_chained(self) -> None:
        conv = await create_conversation(CreateConversationRequest(
            title="Chain test", created_by="ewan", creator_type="human",
        ))
        await add_participant(conv.sheet_id, AddParticipantRequest(
            identity="antigravity", participant_type="agent", role="participant",
        ))
        await send_message(conv.sheet_id, SendMessageRequest(
            content="First message", author="ewan",
        ))
        await send_message(conv.sheet_id, SendMessageRequest(
            content="Second message", author="antigravity",
            epistemic_tier="STRUCTURED",
        ))

        store = get_store()
        sheet = await store.get_sheet(conv.sheet_id)
        assert len(sheet.entries) == 2
        assert HashChain.validate_chain(sheet.entries)

    @pytest.mark.asyncio
    async def test_non_participant_rejected(self) -> None:
        conv = await create_conversation(CreateConversationRequest(
            title="Test", created_by="ewan",
        ))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await send_message(conv.sheet_id, SendMessageRequest(
                content="I shouldn't be here",
                author="intruder",
            ))
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_observer_cannot_send(self) -> None:
        conv = await create_conversation(CreateConversationRequest(
            title="Test", created_by="ewan",
        ))
        await add_participant(conv.sheet_id, AddParticipantRequest(
            identity="auditor", participant_type="agent", role="observer",
        ))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await send_message(conv.sheet_id, SendMessageRequest(
                content="Just watching", author="auditor",
            ))
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Model-to-model conversations
# ---------------------------------------------------------------------------


class TestModelToModel:
    """Agent ↔ Agent conversation under strict epistemic rules."""

    @pytest.mark.asyncio
    async def test_two_models_can_converse(self) -> None:
        conv = await create_conversation(CreateConversationRequest(
            title="Model deliberation",
            created_by="gpt-5.5",
            creator_type="model",
            initial_participants=["claude-opus-4.7"],
        ))
        r1 = await send_message(conv.sheet_id, SendMessageRequest(
            content="I recommend deploying today.",
            author="gpt-5.5",
            epistemic_tier="STRUCTURED",
        ))
        r2 = await send_message(conv.sheet_id, SendMessageRequest(
            content="I disagree — wait for the soak test.",
            author="claude-opus-4.7",
            epistemic_tier="STRUCTURED",
        ))
        assert r1.effective_tier == "STRUCTURED"
        assert r2.effective_tier == "STRUCTURED"

        store = get_store()
        sheet = await store.get_sheet(conv.sheet_id)
        assert len(sheet.entries) == 2
        assert HashChain.validate_chain(sheet.entries)

    @pytest.mark.asyncio
    async def test_model_cannot_claim_measured(self) -> None:
        """Models can't claim MEASURED — that requires measurement pipeline."""
        conv = await create_conversation(CreateConversationRequest(
            title="Tier test",
            created_by="gpt-5.5",
            creator_type="model",
        ))
        resp = await send_message(conv.sheet_id, SendMessageRequest(
            content="My calibrated probability is 0.95",
            author="gpt-5.5",
            epistemic_tier="MEASURED",  # will be capped
        ))
        assert resp.effective_tier == "STRUCTURED"  # capped by model ceiling

    @pytest.mark.asyncio
    async def test_human_in_model_conversation_stays_intuited(self) -> None:
        """Human joins a model conversation — their tier stays INTUITED."""
        conv = await create_conversation(CreateConversationRequest(
            title="Mixed conversation",
            created_by="gpt-5.5",
            creator_type="model",
        ))
        await add_participant(conv.sheet_id, AddParticipantRequest(
            identity="ewan", participant_type="human", role="participant",
        ))
        resp = await send_message(conv.sheet_id, SendMessageRequest(
            content="What do you two think?",
            author="ewan",
            epistemic_tier="STRUCTURED",  # will be capped to INTUITED
        ))
        assert resp.effective_tier == "INTUITED"

    @pytest.mark.asyncio
    async def test_all_messages_attributed_and_immutable(self) -> None:
        """Every message in a model conversation has full attribution."""
        conv = await create_conversation(CreateConversationRequest(
            title="Attribution test",
            created_by="gpt-5.5",
            creator_type="model",
            initial_participants=["claude-opus-4.7", "gemini-3.1"],
        ))
        for author in ["gpt-5.5", "claude-opus-4.7", "gemini-3.1"]:
            await send_message(conv.sheet_id, SendMessageRequest(
                content=f"Analysis from {author}",
                author=author,
                epistemic_tier="STRUCTURED",
            ))

        msgs = await list_messages(conv.sheet_id)
        assert msgs["message_count"] == 3
        authors = [m["author"] for m in msgs["messages"]]
        assert authors == ["gpt-5.5", "claude-opus-4.7", "gemini-3.1"]

        # Every entry has correct metadata
        for m in msgs["messages"]:
            assert m["metadata"]["layer"] == "correspondence"
            assert m["metadata"]["participant_type"] == "model"


# ---------------------------------------------------------------------------
# Epistemic tier enforcement
# ---------------------------------------------------------------------------


class TestEpistemicEnforcement:
    @pytest.mark.asyncio
    async def test_tier_capping_recorded_in_metadata(self) -> None:
        conv = await create_conversation(CreateConversationRequest(
            title="Tier cap test",
            created_by="ewan",
            creator_type="human",
        ))
        resp = await send_message(conv.sheet_id, SendMessageRequest(
            content="I think this is right",
            author="ewan",
            epistemic_tier="MEASURED",  # human can't claim MEASURED
        ))
        assert resp.effective_tier == "INTUITED"

        store = get_store()
        sheet = await store.get_sheet(conv.sheet_id)
        entry = sheet.entries[0]
        assert entry.metadata["tier_capped"] is True
        assert entry.metadata["claimed_tier"] == "MEASURED"
        assert entry.metadata["effective_tier"] == "INTUITED"


# ---------------------------------------------------------------------------
# Participant management
# ---------------------------------------------------------------------------


class TestParticipantManagement:
    @pytest.mark.asyncio
    async def test_add_participant(self) -> None:
        conv = await create_conversation(CreateConversationRequest(
            title="Test", created_by="ewan",
        ))
        resp = await add_participant(conv.sheet_id, AddParticipantRequest(
            identity="devon-9892",
            participant_type="agent",
            role="participant",
        ))
        assert resp.identity == "devon-9892"
        assert resp.max_tier == "STRUCTURED"

    @pytest.mark.asyncio
    async def test_duplicate_participant_rejected(self) -> None:
        conv = await create_conversation(CreateConversationRequest(
            title="Test", created_by="ewan",
        ))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await add_participant(conv.sheet_id, AddParticipantRequest(
                identity="ewan",  # already the owner
            ))
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_list_participants(self) -> None:
        conv = await create_conversation(CreateConversationRequest(
            title="Test", created_by="ewan",
            initial_participants=["antigravity"],
        ))
        resp = await list_participants(conv.sheet_id)
        identities = [p["identity"] for p in resp["participants"]]
        assert "ewan" in identities
        assert "antigravity" in identities

    @pytest.mark.asyncio
    async def test_nonexistent_sheet_returns_404(self) -> None:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await list_participants("nonexistent")
        assert exc_info.value.status_code == 404
