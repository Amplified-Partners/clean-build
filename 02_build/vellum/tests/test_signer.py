# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Tests for Ed25519 entry signing and verification."""

from vellum.models.entry import LedgerEntry
from vellum.signing.keys import generate_keypair, load_signing_key
from vellum.signing.signer import sign_bytes, sign_entry, verify_bytes, verify_entry


def _make_entry(**kwargs: str) -> LedgerEntry:
    defaults = {"author": "test-agent", "entry_type": "test"}
    defaults.update(kwargs)
    return LedgerEntry(**defaults)


class TestSignEntry:
    def test_sign_produces_valid_signature(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entry = _make_entry()
        signed = sign_entry(entry, sk)
        assert signed.signature_hex
        assert signed.public_key_hex == kp.verify_key_hex
        assert signed.entry == entry

    def test_verify_accepts_valid_signature(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entry = _make_entry()
        signed = sign_entry(entry, sk)
        assert verify_entry(signed) is True

    def test_verify_rejects_tampered_content(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entry = _make_entry()
        signed = sign_entry(entry, sk)
        signed.entry.content = {"tampered": True}
        assert verify_entry(signed) is False

    def test_verify_rejects_tampered_signature(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entry = _make_entry()
        signed = sign_entry(entry, sk)
        bad_sig = "00" * 64
        signed.signature_hex = bad_sig
        assert verify_entry(signed) is False

    def test_verify_rejects_wrong_key(self) -> None:
        kp1 = generate_keypair()
        kp2 = generate_keypair()
        sk1 = load_signing_key(kp1.signing_key_hex)
        entry = _make_entry()
        signed = sign_entry(entry, sk1)
        signed.public_key_hex = kp2.verify_key_hex
        assert verify_entry(signed) is False

    def test_deterministic_signature_for_same_key_and_entry(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        entry = _make_entry(
            author="determinism-test",
            entry_type="fixed",
        )
        sig1 = sign_entry(entry, sk)
        sig2 = sign_entry(entry, sk)
        assert sig1.signature_hex == sig2.signature_hex


class TestSignBytes:
    def test_sign_and_verify_bytes(self) -> None:
        from vellum.signing.keys import load_verify_key

        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        vk = load_verify_key(kp.verify_key_hex)
        data = b"arbitrary payload"
        sig = sign_bytes(data, sk)
        assert verify_bytes(data, sig, vk) is True

    def test_verify_bytes_rejects_tampered_data(self) -> None:
        from vellum.signing.keys import load_verify_key

        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        vk = load_verify_key(kp.verify_key_hex)
        sig = sign_bytes(b"original", sk)
        assert verify_bytes(b"tampered", sig, vk) is False
