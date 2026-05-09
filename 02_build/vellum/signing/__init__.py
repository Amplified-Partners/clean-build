# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Vellum Ed25519 signing operations."""

from vellum.signing.keys import generate_keypair, load_signing_key, load_verify_key
from vellum.signing.signer import sign_entry, verify_entry

__all__ = [
    "generate_keypair",
    "load_signing_key",
    "load_verify_key",
    "sign_entry",
    "verify_entry",
]
