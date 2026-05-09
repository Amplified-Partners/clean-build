# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Ed25519 key data models."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class KeyInfo(BaseModel):
    """Public key metadata for verification and key management."""

    schema_version: str = "1.0"
    key_id: str = Field(default_factory=lambda: str(uuid4()))
    public_key_hex: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    label: str = ""
    algorithm: str = "Ed25519"


class KeyPair(BaseModel):
    """Ed25519 keypair for signing operations.

    The private key (signing_key_hex) must NEVER be logged, serialized
    to untrusted storage, or exposed in API responses.
    """

    schema_version: str = "1.0"
    key_id: str = Field(default_factory=lambda: str(uuid4()))
    signing_key_hex: str
    verify_key_hex: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    label: str = ""
    algorithm: str = "Ed25519"

    def to_key_info(self) -> KeyInfo:
        """Extract public KeyInfo (safe to share/publish)."""
        return KeyInfo(
            key_id=self.key_id,
            public_key_hex=self.verify_key_hex,
            created_at=self.created_at,
            label=self.label,
            algorithm=self.algorithm,
        )
