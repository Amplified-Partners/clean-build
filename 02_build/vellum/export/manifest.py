# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Export manifest generation."""

from __future__ import annotations

from vellum.export.formats import canonical_json, content_hash
from vellum.models.entry import SignedEntry
from vellum.models.export_bundle import ExportManifest
from vellum.models.key_info import KeyInfo


def build_manifest(
    entries: list[SignedEntry],
    exporter: str = "",
    exporter_session: str = "",
    tags: list[str] | None = None,
) -> ExportManifest:
    """Build an export manifest from a list of signed entries.

    Computes a content hash over the canonical JSON of all entries
    and collects the unique signing keys used.
    """
    seen_keys: dict[str, KeyInfo] = {}
    for signed in entries:
        pk = signed.public_key_hex
        if pk not in seen_keys:
            seen_keys[pk] = KeyInfo(public_key_hex=pk)

    entries_data = [e.model_dump() for e in entries]
    bundle_hash = content_hash(entries_data)

    return ExportManifest(
        entry_count=len(entries),
        exporter=exporter,
        exporter_session=exporter_session,
        signing_keys=list(seen_keys.values()),
        content_hash=bundle_hash,
        tags=tags or [],
    )
