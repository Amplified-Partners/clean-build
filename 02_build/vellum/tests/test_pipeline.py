# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Tests for the full export pipeline."""

from nacl.signing import VerifyKey

from vellum.export.formats import canonical_json
from vellum.export.pipeline import export_entries
from vellum.models.entry import LedgerEntry
from vellum.signing.keys import generate_keypair, load_signing_key
from vellum.signing.signer import verify_bytes, verify_entry


def _make_entries(n: int = 3) -> list[LedgerEntry]:
    return [
        LedgerEntry(
            author="test-agent",
            entry_type="test",
            content={"index": i},
        )
        for i in range(n)
    ]


class TestExportPipeline:
    def test_export_produces_bundle_with_all_entries(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entries = _make_entries(5)
        bundle = export_entries(entries, sk, exporter="test")
        assert len(bundle.entries) == 5
        assert bundle.manifest.entry_count == 5

    def test_all_entries_have_valid_signatures(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entries = _make_entries(3)
        bundle = export_entries(entries, sk)
        for signed in bundle.entries:
            assert verify_entry(signed) is True

    def test_manifest_has_valid_signature(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entries = _make_entries(2)
        bundle = export_entries(entries, sk)
        vk = VerifyKey(bytes.fromhex(bundle.manifest_public_key_hex))
        manifest_bytes = canonical_json(bundle.manifest.model_dump())
        assert verify_bytes(manifest_bytes, bundle.manifest_signature_hex, vk)

    def test_manifest_signature_detects_tamper(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entries = _make_entries(2)
        bundle = export_entries(entries, sk)
        bundle.manifest.entry_count = 999
        vk = VerifyKey(bytes.fromhex(bundle.manifest_public_key_hex))
        manifest_bytes = canonical_json(bundle.manifest.model_dump())
        assert not verify_bytes(manifest_bytes, bundle.manifest_signature_hex, vk)

    def test_manifest_content_hash_matches_entries(self) -> None:
        """Content hash is the SHA-256 of the canonical JSON of signed entries."""
        from vellum.export.formats import content_hash

        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entries = _make_entries(2)
        bundle = export_entries(entries, sk)
        expected = content_hash([e.model_dump() for e in bundle.entries])
        assert bundle.manifest.content_hash == expected

    def test_manifest_collects_signing_keys(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entries = _make_entries(3)
        bundle = export_entries(entries, sk)
        assert len(bundle.manifest.signing_keys) == 1
        assert bundle.manifest.signing_keys[0].public_key_hex == kp.verify_key_hex

    def test_exporter_metadata_is_recorded(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entries = _make_entries(1)
        bundle = export_entries(
            entries,
            sk,
            exporter="devon-9892",
            exporter_session="session-abc",
            tags=["test", "u13"],
        )
        assert bundle.manifest.exporter == "devon-9892"
        assert bundle.manifest.exporter_session == "session-abc"
        assert bundle.manifest.tags == ["test", "u13"]

    def test_empty_entries_produces_empty_bundle(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        bundle = export_entries([], sk)
        assert len(bundle.entries) == 0
        assert bundle.manifest.entry_count == 0
        assert bundle.manifest_signature_hex != ""

    def test_bundle_roundtrip_serialization(self) -> None:
        """Bundle can be serialized to JSON and deserialized back."""
        from vellum.models.export_bundle import ExportBundle

        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entries = _make_entries(2)
        bundle = export_entries(entries, sk, exporter="roundtrip-test")
        json_str = bundle.model_dump_json()
        restored = ExportBundle.model_validate_json(json_str)
        assert restored.manifest.entry_count == bundle.manifest.entry_count
        assert len(restored.entries) == len(bundle.entries)
        for original, restored_entry in zip(bundle.entries, restored.entries):
            assert verify_entry(restored_entry) is True
            assert original.signature_hex == restored_entry.signature_hex
