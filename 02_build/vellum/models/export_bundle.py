# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Export bundle data models."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from vellum.models.entry import SignedEntry
from vellum.models.key_info import KeyInfo


class ExportManifest(BaseModel):
    """Manifest for an export bundle, providing integrity metadata.

    The manifest itself can be signed to provide bundle-level integrity.
    """

    schema_version: str = "1.0"
    bundle_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    entry_count: int = 0
    exporter: str = ""
    exporter_session: str = ""
    signing_keys: list[KeyInfo] = Field(default_factory=list)
    content_hash: str = ""
    tags: list[str] = Field(default_factory=list)


class ExportBundle(BaseModel):
    """A self-contained export bundle with signed entries and manifest.

    The bundle contains everything needed to verify all entries:
    the signed entries, the signing public keys, and the manifest.
    """

    schema_version: str = "1.0"
    manifest: ExportManifest
    entries: list[SignedEntry] = Field(default_factory=list)
    manifest_signature_hex: str = ""
    manifest_public_key_hex: str = ""
