"""§3.2 — Auth Ulysses boot check.

Proves the two-flag safety: Vellum refuses to start without auth
unless explicitly in dev mode. VELLUM_REQUIRE_AUTH=1 overrides
dev mode entirely — a Ulysses commitment in the boot path.

Dana | 2026-05-20 | P1 test §3.2
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from vellum.app import _check_auth_config


class TestAuthBootCheck:
    """Auth Ulysses boot check — refuses to start without auth."""

    def test_require_auth_without_auth_enabled_refuses(self) -> None:
        """VELLUM_REQUIRE_AUTH=1 but no VELLUM_AUTH_ENABLED → refuse."""
        env = {"VELLUM_REQUIRE_AUTH": "1", "VELLUM_AUTH_ENABLED": "0"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="VELLUM_REQUIRE_AUTH=1"):
                _check_auth_config()

    def test_require_auth_with_auth_enabled_passes(self) -> None:
        """VELLUM_REQUIRE_AUTH=1 + VELLUM_AUTH_ENABLED=1 → production mode."""
        env = {"VELLUM_REQUIRE_AUTH": "1", "VELLUM_AUTH_ENABLED": "1"}
        with patch.dict(os.environ, env, clear=True):
            _check_auth_config()  # should not raise

    def test_require_auth_ignores_dev_mode(self) -> None:
        """VELLUM_REQUIRE_AUTH=1 overrides dev mode."""
        env = {
            "VELLUM_REQUIRE_AUTH": "1",
            "VELLUM_AUTH_ENABLED": "0",
            "VELLUM_DEV_MODE": "1",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="VELLUM_REQUIRE_AUTH=1"):
                _check_auth_config()

    def test_no_auth_no_dev_refuses(self) -> None:
        """Neither auth nor dev mode → refuse to start."""
        env = {"VELLUM_AUTH_ENABLED": "0", "VELLUM_DEV_MODE": "0"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="Auth disabled outside dev mode"):
                _check_auth_config()

    def test_unset_auth_no_dev_refuses(self) -> None:
        """Auth not set at all, no dev mode → refuse."""
        env: dict[str, str] = {}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit, match="Auth disabled outside dev mode"):
                _check_auth_config()

    def test_dev_mode_allows_no_auth(self) -> None:
        """VELLUM_DEV_MODE=1 allows auth to be disabled (dev only)."""
        env = {"VELLUM_DEV_MODE": "1"}
        with patch.dict(os.environ, env, clear=True):
            _check_auth_config()  # should not raise

    def test_auth_enabled_without_require_passes(self) -> None:
        """VELLUM_AUTH_ENABLED=1 without REQUIRE_AUTH → fine."""
        env = {"VELLUM_AUTH_ENABLED": "1"}
        with patch.dict(os.environ, env, clear=True):
            _check_auth_config()  # should not raise
