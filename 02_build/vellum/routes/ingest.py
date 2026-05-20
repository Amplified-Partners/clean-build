"""Ingestion routes — webhook endpoint for external sources.

Receives messages from Cursor, terminal, WhatsApp, Slack, Linear,
or any HTTP client and writes them to correspondence sheets.
Each message becomes a hash-chained, attributed, epistemic-tier-tagged
SheetEntry on the conversation's correspondence sheet.

Auto-provisioning: if a conversation doesn't exist for a source/channel
combination, one is created automatically. Participants are registered
on first message.

Dana | 2026-05-20 | Ingestion routes for Correspondence mode
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from vellum.ingest.connectors import (
    SOURCE_DEFAULTS,
    IngestMessage,
    normalise,
)
from vellum.models.entry import SheetEntry
from vellum.models.participant import Participant
from vellum.models.sheet import SheetMeta
from vellum.routes.correspondence import (
    _add_participant,
    _get_participant,
    _get_participants,
)
from vellum.storage import get_store

log = logging.getLogger("vellum.ingest")
router = APIRouter(prefix="/api/v1", tags=["ingest"])


# ---------------------------------------------------------------------------
# Conversation registry — maps source:channel to sheet_id
# Production: move to Postgres
# ---------------------------------------------------------------------------

_channel_map: dict[str, str] = {}  # "source:channel_key" → sheet_id


def _channel_key(source: str, channel: str) -> str:
    return f"{source}:{channel}"


def clear_channel_map() -> None:
    """For testing."""
    _channel_map.clear()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class WebhookRequest(BaseModel):
    """Generic webhook payload."""
    source: str = Field(..., description="Source type: cursor, terminal, whatsapp, slack, linear, generic")
    channel: str = Field(default="default", description="Channel/conversation identifier from the source")
    payload: dict = Field(..., description="Source-specific message payload")


class WebhookResponse(BaseModel):
    entry_id: str
    entry_hash: str
    sheet_id: str
    author: str
    effective_tier: str
    source: str
    created_conversation: bool = False


class BatchWebhookRequest(BaseModel):
    """Batch ingest multiple messages."""
    source: str
    channel: str = "default"
    messages: list[dict] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/ingest/webhook", response_model=WebhookResponse)
async def ingest_webhook(body: WebhookRequest) -> WebhookResponse:
    """Ingest a message from any external source.

    Normalises the payload, auto-provisions a conversation if needed,
    registers the participant, and writes a hash-chained entry.
    """
    store = get_store()

    # Normalise the payload
    msg = normalise(body.source, body.payload)

    # Find or create conversation
    key = _channel_key(body.source, body.channel)
    created = False
    sheet_id = _channel_map.get(key)

    if sheet_id is None:
        # Auto-provision a new conversation
        meta = SheetMeta(
            title=f"{body.source}/{body.channel}",
            mode="correspondence",
            created_by=f"ingest-{body.source}",
        )
        await store.create_sheet(meta)
        sheet_id = meta.id
        _channel_map[key] = sheet_id
        created = True
        log.info("Auto-provisioned conversation %s for %s", sheet_id, key)

    sheet = await store.get_sheet(sheet_id)
    if sheet is None:
        raise HTTPException(status_code=500, detail="Conversation sheet disappeared")

    # Register participant if not already known
    participant = _get_participant(sheet_id, msg.author)
    if participant is None:
        defaults = SOURCE_DEFAULTS.get(body.source, SOURCE_DEFAULTS["generic"])
        participant = Participant(
            sheet_id=sheet_id,
            identity=msg.author,
            participant_type=defaults["participant_type"],
            role="participant" if not created else "owner",
        )
        _add_participant(participant)
        log.info("Auto-registered participant %s on %s", msg.author, sheet_id)

    # Determine entry type and effective tier
    if participant.participant_type == "human":
        entry_type = "human_comment"
        effective_tier = "INTUITED"
    else:
        entry_type = "agent_write"
        from vellum.models.participant import tier_min
        effective_tier = tier_min(msg.epistemic_tier, participant.max_tier)

    # Write entry
    entry = SheetEntry(
        sheet_id=sheet_id,
        author=msg.author,
        content=msg.content,
        prev_hash=sheet.latest_hash,
        entry_type=entry_type,
        epistemic_tier=effective_tier,
        metadata={
            "layer": "correspondence",
            "source": body.source,
            "channel": body.channel,
            "participant_type": participant.participant_type,
            "claimed_tier": msg.epistemic_tier,
            "effective_tier": effective_tier,
            "tier_capped": msg.epistemic_tier != effective_tier,
            **msg.metadata,
        },
    )
    await store.append_entry(sheet_id, entry)

    return WebhookResponse(
        entry_id=entry.id,
        entry_hash=entry.entry_hash,
        sheet_id=sheet_id,
        author=msg.author,
        effective_tier=effective_tier,
        source=body.source,
        created_conversation=created,
    )


@router.post("/ingest/batch")
async def ingest_batch(body: BatchWebhookRequest) -> dict:
    """Ingest multiple messages from the same source/channel.

    Useful for backfilling conversation history or bulk ingestion.
    Messages are written in order, each chained to the previous.
    """
    results = []
    for payload in body.messages:
        resp = await ingest_webhook(WebhookRequest(
            source=body.source,
            channel=body.channel,
            payload=payload,
        ))
        results.append(resp.model_dump())

    return {
        "status": "ok",
        "count": len(results),
        "sheet_id": results[0]["sheet_id"] if results else None,
        "entries": results,
    }


@router.get("/ingest/channels")
async def list_channels() -> dict:
    """List all active ingestion channels and their sheet mappings."""
    channels = []
    for key, sheet_id in _channel_map.items():
        source, channel = key.split(":", 1)
        channels.append({
            "source": source,
            "channel": channel,
            "sheet_id": sheet_id,
            "participant_count": len(_get_participants(sheet_id)),
        })
    return {"channels": channels, "count": len(channels)}
