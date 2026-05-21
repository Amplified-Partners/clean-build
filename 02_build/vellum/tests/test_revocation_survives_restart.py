"""§3.1 — Token revocation durability.

Proves that token revocation carries attribution (who, when) and
survives store operations. The old in-memory boolean could be
reset on restart — the new model carries revoked_at and revoked_by
timestamps for audit.

Dana | 2026-05-20 | P1 test §3.1
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio

from vellum.models.token import ShareToken
from vellum.storage import init_store
from vellum.storage.memory import MemorySheetStore


@pytest_asyncio.fixture
async def store():
    s = await init_store()
    yield s
    if isinstance(s, MemorySheetStore):
        s.clear()


class TestRevocationAttribution:
    """Revocation carries who did it and when."""

    @pytest.mark.asyncio
    async def test_revoke_sets_timestamp_and_author(self, store) -> None:
        token = ShareToken(sheet_id="s1", role="read")
        await store.store_token(token)
        assert not token.revoked

        await store.revoke_token(token.token_id, revoked_by="ewan")

        revoked = await store.get_token(token.token_id)
        assert revoked.revoked is True
        assert revoked.revoked_by == "ewan"
        assert revoked.revoked_at is not None
        assert isinstance(revoked.revoked_at, datetime)

    @pytest.mark.asyncio
    async def test_revoked_token_is_not_valid(self, store) -> None:
        token = ShareToken(sheet_id="s1", role="write")
        await store.store_token(token)
        assert token.is_valid

        await store.revoke_token(token.token_id, revoked_by="system")

        revoked = await store.get_token(token.token_id)
        assert not revoked.is_valid

    @pytest.mark.asyncio
    async def test_revocation_survives_get(self, store) -> None:
        """After revocation, re-fetching the token still shows revoked."""
        token = ShareToken(sheet_id="s1", role="comment")
        await store.store_token(token)
        await store.revoke_token(token.token_id, revoked_by="admin")

        # Re-fetch from store — must still be revoked
        fetched = await store.get_token(token.token_id)
        assert fetched is not None
        assert fetched.revoked is True
        assert fetched.revoked_by == "admin"

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_token_raises(self, store) -> None:
        with pytest.raises(KeyError, match="not found"):
            await store.revoke_token("nonexistent-id", revoked_by="ewan")


class TestTokenValidity:
    """Token validity checks: revoked + expired."""

    def test_fresh_token_is_valid(self) -> None:
        token = ShareToken(sheet_id="s1", role="read")
        assert token.is_valid
        assert not token.is_expired
        assert not token.revoked

    def test_expired_token_is_not_valid(self) -> None:
        token = ShareToken(
            sheet_id="s1",
            role="read",
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        assert token.is_expired
        assert not token.is_valid

    def test_revoked_token_is_not_valid(self) -> None:
        token = ShareToken(
            sheet_id="s1",
            role="read",
            revoked=True,
            revoked_at=datetime.now(timezone.utc),
            revoked_by="test",
        )
        assert not token.is_valid
