# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Ed25519 key generation and loading via PyNaCl (libsodium)."""

from __future__ import annotations

from nacl.signing import SigningKey, VerifyKey

from vellum.models.key_info import KeyPair


def generate_keypair(label: str = "") -> KeyPair:
    """Generate a new Ed25519 keypair.

    Returns a KeyPair containing both the signing (private) and verify (public)
    keys in hex encoding.
    """
    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key

    return KeyPair(
        signing_key_hex=signing_key.encode().hex(),
        verify_key_hex=verify_key.encode().hex(),
        label=label,
    )


def load_signing_key(hex_key: str) -> SigningKey:
    """Load an Ed25519 signing key from hex-encoded bytes."""
    return SigningKey(bytes.fromhex(hex_key))


def load_verify_key(hex_key: str) -> VerifyKey:
    """Load an Ed25519 verify key from hex-encoded bytes."""
    return VerifyKey(bytes.fromhex(hex_key))
