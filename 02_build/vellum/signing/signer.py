# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Ed25519 signing and verification of ledger entries."""

from __future__ import annotations

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from vellum.export.formats import canonical_json
from vellum.models.entry import LedgerEntry, SignedEntry


def sign_entry(entry: LedgerEntry, signing_key: SigningKey) -> SignedEntry:
    """Sign a ledger entry with an Ed25519 key.

    Serializes the entry to canonical JSON, signs the bytes, and returns
    a SignedEntry wrapping the original entry with the signature.
    """
    payload = canonical_json(entry.model_dump())
    signed = signing_key.sign(payload)
    verify_key = signing_key.verify_key

    return SignedEntry(
        entry=entry,
        signature_hex=signed.signature.hex(),
        public_key_hex=verify_key.encode().hex(),
    )


def verify_entry(signed_entry: SignedEntry) -> bool:
    """Verify the Ed25519 signature on a signed ledger entry.

    Reconstructs the canonical JSON payload from the entry and checks
    the signature against the embedded public key. Returns True if valid.
    """
    verify_key = VerifyKey(bytes.fromhex(signed_entry.public_key_hex))
    payload = canonical_json(signed_entry.entry.model_dump())
    signature = bytes.fromhex(signed_entry.signature_hex)

    try:
        verify_key.verify(payload, signature)
        return True
    except BadSignatureError:
        return False


def sign_bytes(data: bytes, signing_key: SigningKey) -> str:
    """Sign arbitrary bytes, returning the signature as hex."""
    signed = signing_key.sign(data)
    return signed.signature.hex()


def verify_bytes(data: bytes, signature_hex: str, verify_key: VerifyKey) -> bool:
    """Verify a signature on arbitrary bytes."""
    try:
        verify_key.verify(data, bytes.fromhex(signature_hex))
        return True
    except BadSignatureError:
        return False
