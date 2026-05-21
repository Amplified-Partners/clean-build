"""Ingestion connector and webhook tests.

Covers:
  - Normalisation of payloads from each source (cursor, terminal,
    whatsapp, slack, linear, generic)
  - Webhook endpoint: auto-provisioning, participant registration,
    hash chain integrity, tier enforcement
  - Batch ingestion
  - Channel listing

Dana | 2026-05-20 | Ingestion tests
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from vellum.canvas.hash_chain import HashChain
from vellum.ingest.connectors import (
    normalise,
    normalise_cursor,
    normalise_slack,
    normalise_terminal,
    normalise_whatsapp,
    verify_webhook_signature,
)
from vellum.routes.correspondence import clear_participants
from vellum.routes.ingest import (
    BatchWebhookRequest,
    WebhookRequest,
    clear_channel_map,
    ingest_batch,
    ingest_webhook,
    list_channels,
)
from vellum.storage import get_store, init_store
from vellum.storage.memory import MemorySheetStore


@pytest_asyncio.fixture(autouse=True)
async def _setup():
    store = await init_store()
    yield
    clear_participants()
    clear_channel_map()
    if isinstance(store, MemorySheetStore):
        store.clear()


# ---------------------------------------------------------------------------
# Connector normalisation
# ---------------------------------------------------------------------------


class TestConnectors:
    def test_cursor_normalise(self) -> None:
        msg = normalise_cursor({
            "agent_name": "antigravity",
            "content": "Morning brief ready",
            "session_id": "sess-123",
        })
        assert msg.source == "cursor"
        assert msg.author == "antigravity"
        assert msg.content == "Morning brief ready"
        assert msg.participant_type == "agent"
        assert msg.epistemic_tier == "STRUCTURED"

    def test_terminal_normalise(self) -> None:
        msg = normalise_terminal({
            "agent_name": "devon-9892",
            "content": "Tests passing",
            "session_id": "devin-abc",
        })
        assert msg.source == "terminal"
        assert msg.author == "devon-9892"
        assert msg.epistemic_tier == "STRUCTURED"

    def test_whatsapp_normalise(self) -> None:
        msg = normalise_whatsapp({
            "data": {
                "pushName": "Ewan",
                "from": "447700900000",
                "message": {"conversation": "What's the plan today?"},
            }
        })
        assert msg.source == "whatsapp"
        assert msg.author == "Ewan"
        assert msg.content == "What's the plan today?"
        assert msg.epistemic_tier == "INTUITED"
        assert msg.participant_type == "human"

    def test_slack_normalise(self) -> None:
        msg = normalise_slack({
            "event": {
                "user_name": "ewan",
                "text": "Check the latest build",
                "channel": "C123",
            }
        })
        assert msg.source == "slack"
        assert msg.author == "ewan"
        assert msg.epistemic_tier == "INTUITED"

    def test_generic_fallback(self) -> None:
        msg = normalise("unknown_source", {"author": "bot", "content": "hello"})
        assert msg.source == "generic"
        assert msg.author == "bot"


# ---------------------------------------------------------------------------
# Webhook signature verification
# ---------------------------------------------------------------------------


class TestSignatureVerification:
    def test_valid_signature(self) -> None:
        import hashlib
        import hmac
        payload = b'{"test": true}'
        secret = "my-secret"
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(payload, sig, secret) is True

    def test_invalid_signature(self) -> None:
        assert verify_webhook_signature(b"data", "wrong", "secret") is False


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------


class TestWebhookEndpoint:
    @pytest.mark.asyncio
    async def test_auto_provisions_conversation(self) -> None:
        resp = await ingest_webhook(WebhookRequest(
            source="cursor",
            channel="antigravity-session",
            payload={"agent_name": "antigravity", "content": "Hello from Cursor"},
        ))
        assert resp.created_conversation is True
        assert resp.source == "cursor"
        assert resp.author == "antigravity"
        assert resp.effective_tier == "STRUCTURED"

    @pytest.mark.asyncio
    async def test_reuses_existing_conversation(self) -> None:
        r1 = await ingest_webhook(WebhookRequest(
            source="terminal",
            channel="devon-session",
            payload={"agent_name": "devon", "content": "First message"},
        ))
        r2 = await ingest_webhook(WebhookRequest(
            source="terminal",
            channel="devon-session",
            payload={"agent_name": "devon", "content": "Second message"},
        ))
        assert r1.sheet_id == r2.sheet_id
        assert r1.created_conversation is True
        assert r2.created_conversation is False

    @pytest.mark.asyncio
    async def test_human_messages_are_intuited(self) -> None:
        resp = await ingest_webhook(WebhookRequest(
            source="whatsapp",
            channel="ewan-phone",
            payload={
                "data": {
                    "pushName": "Ewan",
                    "from": "447700900000",
                    "message": {"conversation": "How's the build going?"},
                }
            },
        ))
        assert resp.effective_tier == "INTUITED"
        assert resp.author == "Ewan"

    @pytest.mark.asyncio
    async def test_messages_are_hash_chained(self) -> None:
        for i in range(3):
            await ingest_webhook(WebhookRequest(
                source="cursor",
                channel="chain-test",
                payload={"agent_name": "ag", "content": f"Message {i}"},
            ))

        store = get_store()
        channels = await list_channels()
        sheet_id = channels["channels"][0]["sheet_id"]
        sheet = await store.get_sheet(sheet_id)
        assert len(sheet.entries) == 3
        assert HashChain.validate_chain(sheet.entries)

    @pytest.mark.asyncio
    async def test_multiple_participants_auto_registered(self) -> None:
        channel = "team-chat"
        for author in ["antigravity", "devon", "cassian"]:
            await ingest_webhook(WebhookRequest(
                source="cursor",
                channel=channel,
                payload={"agent_name": author, "content": f"Hello from {author}"},
            ))

        channels = await list_channels()
        ch = [c for c in channels["channels"] if c["channel"] == channel][0]
        assert ch["participant_count"] == 3


# ---------------------------------------------------------------------------
# Batch ingestion
# ---------------------------------------------------------------------------


class TestBatchIngestion:
    @pytest.mark.asyncio
    async def test_batch_ingest(self) -> None:
        resp = await ingest_batch(BatchWebhookRequest(
            source="terminal",
            channel="backfill",
            messages=[
                {"agent_name": "devon", "content": "Entry 1"},
                {"agent_name": "devon", "content": "Entry 2"},
                {"agent_name": "devon", "content": "Entry 3"},
            ],
        ))
        assert resp["count"] == 3
        assert resp["sheet_id"] is not None

        # Verify chain integrity
        store = get_store()
        sheet = await store.get_sheet(resp["sheet_id"])
        assert HashChain.validate_chain(sheet.entries)


# ---------------------------------------------------------------------------
# Channel listing
# ---------------------------------------------------------------------------


class TestChannelListing:
    @pytest.mark.asyncio
    async def test_list_channels(self) -> None:
        await ingest_webhook(WebhookRequest(
            source="cursor", channel="ch1",
            payload={"agent_name": "ag", "content": "test"},
        ))
        await ingest_webhook(WebhookRequest(
            source="slack", channel="ch2",
            payload={"event": {"user_name": "ewan", "text": "test"}},
        ))

        resp = await list_channels()
        assert resp["count"] == 2
        sources = {c["source"] for c in resp["channels"]}
        assert sources == {"cursor", "slack"}
