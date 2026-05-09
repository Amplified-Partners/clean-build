# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Export pipeline — sign entries and produce a verifiable bundle."""

from __future__ import annotations

from nacl.signing import SigningKey

from vellum.export.formats import canonical_json
from vellum.export.manifest import build_manifest
from vellum.models.entry import LedgerEntry, SignedEntry
from vellum.models.export_bundle import ExportBundle
from vellum.signing.signer import sign_bytes, sign_entry


def export_entries(
    entries: list[LedgerEntry],
    signing_key: SigningKey,
    exporter: str = "",
    exporter_session: str = "",
    tags: list[str] | None = None,
) -> ExportBundle:
    """Run the full export pipeline: sign each entry, build manifest, sign manifest.

    Steps:
    1. Sign each LedgerEntry with the provided Ed25519 key.
    2. Build an ExportManifest with entry count, content hash, and key info.
    3. Sign the manifest itself for bundle-level integrity.
    4. Return a self-contained ExportBundle.
    """
    signed_entries: list[SignedEntry] = []
    for entry in entries:
        signed = sign_entry(entry, signing_key)
        signed_entries.append(signed)

    manifest = build_manifest(
        entries=signed_entries,
        exporter=exporter,
        exporter_session=exporter_session,
        tags=tags,
    )

    manifest_bytes = canonical_json(manifest.model_dump())
    manifest_sig = sign_bytes(manifest_bytes, signing_key)
    verify_key_hex = signing_key.verify_key.encode().hex()

    return ExportBundle(
        manifest=manifest,
        entries=signed_entries,
        manifest_signature_hex=manifest_sig,
        manifest_public_key_hex=verify_key_hex,
    )
