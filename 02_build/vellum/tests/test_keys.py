# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Tests for Ed25519 key generation and loading."""

from nacl.signing import SigningKey, VerifyKey

from vellum.signing.keys import generate_keypair, load_signing_key, load_verify_key


class TestGenerateKeypair:
    def test_returns_keypair_with_hex_keys(self) -> None:
        kp = generate_keypair()
        assert len(kp.signing_key_hex) == 64  # 32 bytes hex
        assert len(kp.verify_key_hex) == 64
        assert kp.algorithm == "Ed25519"

    def test_label_is_stored(self) -> None:
        kp = generate_keypair(label="test-key")
        assert kp.label == "test-key"

    def test_each_call_produces_unique_keys(self) -> None:
        kp1 = generate_keypair()
        kp2 = generate_keypair()
        assert kp1.signing_key_hex != kp2.signing_key_hex
        assert kp1.verify_key_hex != kp2.verify_key_hex
        assert kp1.key_id != kp2.key_id

    def test_to_key_info_strips_private_key(self) -> None:
        kp = generate_keypair(label="public-safe")
        info = kp.to_key_info()
        assert info.public_key_hex == kp.verify_key_hex
        assert info.label == "public-safe"
        assert info.algorithm == "Ed25519"
        assert not hasattr(info, "signing_key_hex")


class TestLoadKeys:
    def test_roundtrip_signing_key(self) -> None:
        kp = generate_keypair()
        loaded = load_signing_key(kp.signing_key_hex)
        assert isinstance(loaded, SigningKey)
        assert loaded.encode().hex() == kp.signing_key_hex

    def test_roundtrip_verify_key(self) -> None:
        kp = generate_keypair()
        loaded = load_verify_key(kp.verify_key_hex)
        assert isinstance(loaded, VerifyKey)
        assert loaded.encode().hex() == kp.verify_key_hex

    def test_loaded_key_can_sign_and_verify(self) -> None:
        kp = generate_keypair()
        sk = load_signing_key(kp.signing_key_hex)
        vk = load_verify_key(kp.verify_key_hex)
        signed = sk.sign(b"test message")
        vk.verify(signed.message, signed.signature)
