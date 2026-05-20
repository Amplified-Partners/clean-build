"""Ingestion connectors — how external messages get into Vellum.

Each connector normalises a source-specific payload into a standard
IngestMessage, which the webhook route writes to a correspondence
sheet as a SheetEntry. The entry inherits the source's epistemic
tier (human speech = INTUITED, agent structured output = STRUCTURED).

Supported sources:
  - cursor    — Antigravity / any Cursor agent session
  - terminal  — Devin / Devon terminal sessions
  - whatsapp  — WhatsApp via Evolution API webhook
  - slack     — Slack messages via webhook
  - linear    — Linear comments/updates via webhook
  - generic   — any HTTP client that posts JSON

Dana | 2026-05-20 | Ingestion connectors for Correspondence mode
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

log = logging.getLogger("vellum.ingest")

SourceType = Literal[
    "cursor", "terminal", "whatsapp", "slack", "linear", "generic",
]

# Source → default participant type and epistemic tier
SOURCE_DEFAULTS: dict[str, dict] = {
    "cursor": {"participant_type": "agent", "default_tier": "STRUCTURED"},
    "terminal": {"participant_type": "agent", "default_tier": "STRUCTURED"},
    "whatsapp": {"participant_type": "human", "default_tier": "INTUITED"},
    "slack": {"participant_type": "human", "default_tier": "INTUITED"},
    "linear": {"participant_type": "agent", "default_tier": "STRUCTURED"},
    "generic": {"participant_type": "agent", "default_tier": "INTUITED"},
}


class IngestMessage(BaseModel):
    """Normalised message from any external source."""

    source: SourceType
    author: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    epistemic_tier: str = "INTUITED"
    participant_type: str = "human"
    raw_payload: dict = Field(default_factory=dict, description="Original payload for audit")
    metadata: dict = Field(default_factory=dict)


def normalise_cursor(payload: dict) -> IngestMessage:
    """Normalise a Cursor agent session message."""
    return IngestMessage(
        source="cursor",
        author=payload.get("agent_name", payload.get("author", "cursor-agent")),
        content=payload.get("content", payload.get("message", "")),
        epistemic_tier=payload.get("epistemic_tier", "STRUCTURED"),
        participant_type="agent",
        raw_payload=payload,
        metadata={
            "session_id": payload.get("session_id", ""),
            "workspace": payload.get("workspace", ""),
        },
    )


def normalise_terminal(payload: dict) -> IngestMessage:
    """Normalise a terminal/Devin session message."""
    return IngestMessage(
        source="terminal",
        author=payload.get("agent_name", payload.get("author", "devon")),
        content=payload.get("content", payload.get("message", "")),
        epistemic_tier=payload.get("epistemic_tier", "STRUCTURED"),
        participant_type="agent",
        raw_payload=payload,
        metadata={
            "session_id": payload.get("session_id", ""),
            "command": payload.get("command", ""),
        },
    )


def normalise_whatsapp(payload: dict) -> IngestMessage:
    """Normalise a WhatsApp Evolution API webhook payload."""
    # Evolution API sends nested structure
    data = payload.get("data", payload)
    message = data.get("message", data)

    content = ""
    if isinstance(message, dict):
        content = (
            message.get("conversation", "")
            or message.get("extendedTextMessage", {}).get("text", "")
            or message.get("body", "")
        )
    elif isinstance(message, str):
        content = message

    return IngestMessage(
        source="whatsapp",
        author=data.get("pushName", data.get("from", "unknown")),
        content=content,
        epistemic_tier="INTUITED",  # Human speech is always INTUITED
        participant_type="human",
        raw_payload=payload,
        metadata={
            "phone": data.get("from", ""),
            "message_id": data.get("key", {}).get("id", "") if isinstance(data.get("key"), dict) else "",
        },
    )


def normalise_slack(payload: dict) -> IngestMessage:
    """Normalise a Slack webhook/event payload."""
    event = payload.get("event", payload)
    return IngestMessage(
        source="slack",
        author=event.get("user_name", event.get("user", "unknown")),
        content=event.get("text", ""),
        epistemic_tier="INTUITED",  # Slack messages are human speech
        participant_type="human",
        raw_payload=payload,
        metadata={
            "channel": event.get("channel", ""),
            "thread_ts": event.get("thread_ts", ""),
            "ts": event.get("ts", ""),
        },
    )


def normalise_linear(payload: dict) -> IngestMessage:
    """Normalise a Linear webhook payload (comment or update)."""
    data = payload.get("data", payload)
    return IngestMessage(
        source="linear",
        author=data.get("user", {}).get("name", "linear") if isinstance(data.get("user"), dict) else "linear",
        content=data.get("body", data.get("description", "")),
        epistemic_tier="STRUCTURED",
        participant_type="agent",
        raw_payload=payload,
        metadata={
            "issue_id": data.get("issue", {}).get("identifier", "") if isinstance(data.get("issue"), dict) else "",
            "action": payload.get("action", ""),
            "type": payload.get("type", ""),
        },
    )


def normalise_generic(payload: dict) -> IngestMessage:
    """Normalise a generic JSON payload."""
    defaults = SOURCE_DEFAULTS["generic"]
    return IngestMessage(
        source="generic",
        author=payload.get("author", "unknown"),
        content=payload.get("content", payload.get("message", "")),
        epistemic_tier=payload.get("epistemic_tier", defaults["default_tier"]),
        participant_type=payload.get("participant_type", defaults["participant_type"]),
        raw_payload=payload,
        metadata=payload.get("metadata", {}),
    )


# Connector registry
CONNECTORS: dict[str, callable] = {
    "cursor": normalise_cursor,
    "terminal": normalise_terminal,
    "whatsapp": normalise_whatsapp,
    "slack": normalise_slack,
    "linear": normalise_linear,
    "generic": normalise_generic,
}


def normalise(source: str, payload: dict) -> IngestMessage:
    """Route a payload to the appropriate connector.

    Falls back to generic if source is unknown.
    """
    connector = CONNECTORS.get(source, normalise_generic)
    return connector(payload)


def verify_webhook_signature(
    payload_body: bytes,
    signature: str,
    secret: str,
    algorithm: str = "sha256",
) -> bool:
    """Verify an HMAC webhook signature.

    Used by WhatsApp (Evolution API), Slack, Linear, and GitHub webhooks.
    """
    expected = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        getattr(hashlib, algorithm),
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
