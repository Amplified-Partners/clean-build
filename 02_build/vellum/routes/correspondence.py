"""Correspondence mode — bidirectional conversation on Vellum sheets.

Supports:
  - Human ↔ Agent (Ewan + Antigravity, Ewan + Devin)
  - Agent ↔ Agent (model-to-model under strict epistemic rules)
  - Human ↔ Human (rare, but supported)

Every message is a SheetEntry on a correspondence-mode sheet:
hash-chained, attributed, epistemic-tier-tagged, immutable.
The conversation IS the audit trail.

Strict rules for model-to-model:
  1. Every message attributed to the sending participant
  2. Epistemic tier capped by participant type (human=INTUITED, agent/model=STRUCTURED)
  3. Min-rule enforced: effective_tier = min(claimed_tier, participant_ceiling)
  4. Observers (role=observer) cannot send messages
  5. All messages hash-chained and immutable

Dana | 2026-05-20 | Correspondence mode — built per Ewan's directive
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vellum.models.entry import SheetEntry
from vellum.models.participant import (
    Participant,
    ParticipantRole,
    ParticipantType,
    TIER_CEILING,
    _TIER_ORDER,
    tier_min,
)
from vellum.models.sheet import SheetMeta
from vellum.storage import get_store

log = logging.getLogger("vellum.correspondence")
router = APIRouter(prefix="/api/v1", tags=["correspondence"])


# ---------------------------------------------------------------------------
# In-memory participant registry (same pattern as token store)
# Production: move to Postgres alongside sheets
# ---------------------------------------------------------------------------

_participants: dict[str, list[Participant]] = {}  # sheet_id → participants


def _get_participants(sheet_id: str) -> list[Participant]:
    return _participants.get(sheet_id, [])


def _get_participant(sheet_id: str, identity: str) -> Participant | None:
    for p in _get_participants(sheet_id):
        if p.identity == identity and p.active:
            return p
    return None


def _add_participant(participant: Participant) -> None:
    if participant.sheet_id not in _participants:
        _participants[participant.sheet_id] = []
    _participants[participant.sheet_id].append(participant)


def clear_participants() -> None:
    """For testing."""
    _participants.clear()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateConversationRequest(BaseModel):
    """Create a new correspondence conversation."""
    title: str = Field(..., min_length=1, description="Conversation title")
    created_by: str = Field(..., description="Identity of the creator")
    creator_type: ParticipantType = Field(default="human")
    initial_participants: list[str] = Field(
        default_factory=list,
        description="Additional participant identities to add at creation",
    )


class CreateConversationResponse(BaseModel):
    sheet_id: str
    title: str
    participants: list[str]


class SendMessageRequest(BaseModel):
    """Send a message on a correspondence sheet."""
    content: str = Field(..., min_length=1, description="Message content")
    author: str = Field(..., description="Participant identity sending the message")
    epistemic_tier: str = Field(
        default="INTUITED",
        description="Claimed epistemic tier — will be capped by participant ceiling",
    )
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class SendMessageResponse(BaseModel):
    entry_id: str
    entry_hash: str
    author: str
    effective_tier: str
    timestamp: datetime


class AddParticipantRequest(BaseModel):
    """Add a participant to a conversation."""
    identity: str = Field(..., description="Participant identity")
    display_name: str = Field(default="", description="Human-readable name")
    participant_type: ParticipantType = Field(default="agent")
    role: ParticipantRole = Field(default="participant")


class ParticipantInfo(BaseModel):
    identity: str
    display_name: str
    participant_type: str
    role: str
    max_tier: str
    active: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/correspondence", response_model=CreateConversationResponse)
async def create_conversation(body: CreateConversationRequest) -> CreateConversationResponse:
    """Create a new correspondence conversation.

    Creates a correspondence-mode sheet and registers the creator
    as the owner. Additional participants can be added at creation
    or later via the participants endpoint.
    """
    store = get_store()

    meta = SheetMeta(
        title=body.title,
        mode="correspondence",
        created_by=body.created_by,
    )
    await store.create_sheet(meta)

    # Register creator as owner
    creator = Participant(
        sheet_id=meta.id,
        identity=body.created_by,
        participant_type=body.creator_type,
        role="owner",
    )
    _add_participant(creator)

    # Register initial participants — inherit creator's type unless overridden later
    participant_identities = [body.created_by]
    for p_identity in body.initial_participants:
        if p_identity == body.created_by:
            continue
        p = Participant(
            sheet_id=meta.id,
            identity=p_identity,
            participant_type=body.creator_type,
            role="participant",
        )
        _add_participant(p)
        participant_identities.append(p_identity)

    log.info(
        "Conversation created: %s (%s) with %d participants",
        meta.id, body.title, len(participant_identities),
    )

    return CreateConversationResponse(
        sheet_id=meta.id,
        title=body.title,
        participants=participant_identities,
    )


@router.post("/correspondence/{sheet_id}/message", response_model=SendMessageResponse)
async def send_message(sheet_id: str, body: SendMessageRequest) -> SendMessageResponse:
    """Send a message on a correspondence sheet.

    Enforces:
    1. Sender must be a registered, active participant (not observer)
    2. Epistemic tier capped by participant ceiling (min-rule)
    3. Message is hash-chained onto the sheet
    """
    store = get_store()
    sheet = await store.get_sheet(sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail=f"Conversation {sheet_id} not found")
    if sheet.meta.mode != "correspondence":
        raise HTTPException(
            status_code=400,
            detail=f"Sheet {sheet_id} is mode={sheet.meta.mode!r}, not correspondence",
        )

    # Check participant is registered and active
    participant = _get_participant(sheet_id, body.author)
    if participant is None:
        raise HTTPException(
            status_code=403,
            detail=f"'{body.author}' is not a participant in this conversation",
        )
    if participant.role == "observer":
        raise HTTPException(
            status_code=403,
            detail=f"'{body.author}' is an observer and cannot send messages",
        )

    # Min-rule: cap claimed tier by participant ceiling
    effective_tier = tier_min(body.epistemic_tier, participant.max_tier)

    # Determine entry type based on participant type
    if participant.participant_type == "human":
        entry_type = "human_comment"
    else:
        entry_type = "agent_write"

    entry = SheetEntry(
        sheet_id=sheet_id,
        author=body.author,
        content=body.content,
        prev_hash=sheet.latest_hash,
        entry_type=entry_type,
        epistemic_tier=effective_tier,
        metadata={
            "layer": "correspondence",
            "participant_type": participant.participant_type,
            "claimed_tier": body.epistemic_tier,
            "effective_tier": effective_tier,
            "tier_capped": body.epistemic_tier != effective_tier,
            **body.metadata,
        },
    )
    await store.append_entry(sheet_id, entry)

    if body.epistemic_tier != effective_tier:
        log.info(
            "Tier capped for %s: claimed %s → effective %s (ceiling: %s)",
            body.author, body.epistemic_tier, effective_tier, participant.max_tier,
        )

    return SendMessageResponse(
        entry_id=entry.id,
        entry_hash=entry.entry_hash,
        author=body.author,
        effective_tier=effective_tier,
        timestamp=entry.timestamp,
    )


@router.get("/correspondence/{sheet_id}/messages")
async def list_messages(sheet_id: str) -> dict:
    """List all messages in a correspondence conversation."""
    store = get_store()
    sheet = await store.get_sheet(sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail=f"Conversation {sheet_id} not found")

    messages = []
    for entry in sheet.entries:
        messages.append({
            "entry_id": entry.id,
            "author": entry.author,
            "content": entry.content,
            "timestamp": entry.timestamp.isoformat(),
            "entry_type": entry.entry_type,
            "epistemic_tier": entry.epistemic_tier,
            "entry_hash": entry.entry_hash,
            "metadata": entry.metadata,
        })

    return {
        "sheet_id": sheet_id,
        "title": sheet.meta.title,
        "mode": sheet.meta.mode,
        "message_count": len(messages),
        "participants": [
            p.identity for p in _get_participants(sheet_id) if p.active
        ],
        "messages": messages,
    }


@router.post("/correspondence/{sheet_id}/participants", response_model=ParticipantInfo)
async def add_participant(sheet_id: str, body: AddParticipantRequest) -> ParticipantInfo:
    """Add a participant to a correspondence conversation.

    Participants can be humans, agents, or models. Each type has
    a tier ceiling enforced by the min-rule.
    """
    store = get_store()
    sheet = await store.get_sheet(sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail=f"Conversation {sheet_id} not found")

    # Check if already a participant
    existing = _get_participant(sheet_id, body.identity)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"'{body.identity}' is already a participant",
        )

    participant = Participant(
        sheet_id=sheet_id,
        identity=body.identity,
        display_name=body.display_name or body.identity,
        participant_type=body.participant_type,
        role=body.role,
    )
    _add_participant(participant)

    log.info(
        "Participant added to %s: %s (%s, %s, max_tier=%s)",
        sheet_id, body.identity, body.participant_type, body.role, participant.max_tier,
    )

    return ParticipantInfo(
        identity=participant.identity,
        display_name=participant.display_name,
        participant_type=participant.participant_type,
        role=participant.role,
        max_tier=participant.max_tier,
        active=participant.active,
    )


@router.get("/correspondence/{sheet_id}/participants")
async def list_participants(sheet_id: str) -> dict:
    """List all participants in a correspondence conversation."""
    store = get_store()
    sheet = await store.get_sheet(sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail=f"Conversation {sheet_id} not found")

    participants = [
        ParticipantInfo(
            identity=p.identity,
            display_name=p.display_name,
            participant_type=p.participant_type,
            role=p.role,
            max_tier=p.max_tier,
            active=p.active,
        )
        for p in _get_participants(sheet_id)
    ]

    return {
        "sheet_id": sheet_id,
        "participants": [p.model_dump() for p in participants],
    }
