"""JWT token creation and validation for Vellum share links.

HS256 tokens scoped to a single sheet with role (read/comment/write),
optional binding to phone/email, and time-based expiry. Revocation
is tracked in-memory here; production should back this with PostgreSQL.

Signed-by: Devon-8c5f | 2026-05-11 | AMP-324
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt

from vellum.models.token import ShareToken, TokenRole

_DEFAULT_TTL_HOURS = 72
_ALGORITHM = "HS256"


def _get_secret() -> str:
    """Resolve the signing secret from env or raise."""
    secret = os.environ.get("VELLUM_JWT_SECRET")
    if not secret:
        raise RuntimeError("VELLUM_JWT_SECRET environment variable is required")
    return secret


class TokenValidationError(Exception):
    """Raised when a JWT fails validation."""


class TokenManager:
    """Create, validate, and revoke sheet-scoped JWTs."""

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    async def create_token(
        self,
        sheet_id: str,
        role: TokenRole = "read",
        bound_to: str | None = None,
        ttl: int | None = None,
    ) -> tuple[str, ShareToken]:
        """Mint a new JWT for *sheet_id*.

        Returns (jwt_string, ShareToken metadata).
        *ttl* is seconds until expiry (default 72 h).
        """
        secret = _get_secret()
        token_id = str(uuid4())
        now = datetime.now(timezone.utc)
        ttl_seconds = ttl if ttl is not None else _DEFAULT_TTL_HOURS * 3600
        expires_at = now + timedelta(seconds=ttl_seconds)

        payload: dict[str, Any] = {
            "jti": token_id,
            "sheet_id": sheet_id,
            "role": role,
            "bound_to": bound_to,
            "iat": now,
            "exp": expires_at,
        }

        token_str = jwt.encode(payload, secret, algorithm=_ALGORITHM)

        share_token = ShareToken(
            token_id=token_id,
            sheet_id=sheet_id,
            role=role,
            bound_to=bound_to,
            expires_at=expires_at,
        )

        return token_str, share_token

    async def validate_token(self, token_str: str) -> dict[str, Any]:
        """Decode and validate a JWT.

        Returns the decoded payload dict on success.
        Raises TokenValidationError on any failure (expired, bad
        signature, revoked, malformed).
        """
        secret = _get_secret()
        try:
            payload = jwt.decode(
                token_str,
                secret,
                algorithms=[_ALGORITHM],
                options={"require": ["jti", "sheet_id", "role", "exp"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenValidationError("Token has expired") from exc
        except jwt.InvalidTokenError as exc:
            raise TokenValidationError(f"Invalid token: {exc}") from exc

        token_id = payload.get("jti", "")
        if token_id in self._revoked:
            raise TokenValidationError("Token has been revoked")

        return payload

    async def revoke_token(self, token_id: str) -> None:
        """Revoke a token by its jti claim.

        Revoked tokens fail validation immediately. In production
        this set should be backed by PostgreSQL or Redis.
        """
        self._revoked.add(token_id)

    async def is_revoked(self, token_id: str) -> bool:
        """Check whether a token_id has been revoked."""
        return token_id in self._revoked
