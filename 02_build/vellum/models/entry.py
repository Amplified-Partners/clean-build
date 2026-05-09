# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Ledger entry data models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class LedgerEntry(BaseModel):
    """A single entry in the Vellum governance ledger.

    Follows the metadata envelope pattern from the Unified Data Architecture.
    """

    schema_version: str = "1.0"
    entry_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    author: str
    author_session: str = ""
    entry_type: str = "generic"
    content: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""
    parent_id: str = ""
    tags: list[str] = Field(default_factory=list)


class SignedEntry(BaseModel):
    """A ledger entry with an Ed25519 cryptographic signature.

    The signature covers the canonical JSON serialization of the entry,
    ensuring tamper-evidence and non-repudiation.
    """

    schema_version: str = "1.0"
    entry: LedgerEntry
    signature_hex: str
    public_key_hex: str
    signed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
