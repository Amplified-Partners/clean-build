"""Portable spine generator stub.

Generates a spine document with explicit includes and excludes.
Every spine carries a valid_until timestamp — no stale spines.

This is the stub shape. Canonical spine shape requires Ewan sign-off
(IMPLEMENTATION_PLAN.md § PR 6). The stub satisfies the state machine
tests and proves the include/exclude/expiry mechanism works.

Known components (from Ewan, 2026-05-19):
  - Steady stomach
  - Five Rods
  - The Amplified Weight
  - Portable brain

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Spine model
# ---------------------------------------------------------------------------


class PortableSpine(BaseModel):
    """A portable spine snapshot.

    Explicit about what it includes AND what it omits.
    """

    spine_id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    valid_until: datetime

    # Explicit includes
    current_state: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    approval_tier: str = "act"

    # Explicit excludes (documented omissions)
    excluded: list[str] = Field(default_factory=list)

    # Freeform sections
    sections: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.valid_until


# ---------------------------------------------------------------------------
# Default excludes — things a spine must NOT carry
# ---------------------------------------------------------------------------

DEFAULT_EXCLUDES: list[str] = [
    "raw_transcript",
    "stale_packets",
    "unscoped_opinions",
    "direct_crm_records",
]


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def generate_spine(
    *,
    current_state: str,
    evidence_refs: list[str] | None = None,
    constraints: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    open_questions: list[str] | None = None,
    approval_tier: str = "act",
    ttl: timedelta = timedelta(hours=24),
    extra_excludes: list[str] | None = None,
    sections: dict[str, Any] | None = None,
) -> PortableSpine:
    """Generate a portable spine with explicit includes and excludes.

    The spine is valid for `ttl` from generation time.
    """
    excludes = list(DEFAULT_EXCLUDES)
    if extra_excludes:
        excludes.extend(extra_excludes)

    return PortableSpine(
        valid_until=datetime.now(timezone.utc) + ttl,
        current_state=current_state,
        evidence_refs=evidence_refs or [],
        constraints=constraints or [],
        allowed_tools=allowed_tools or [],
        open_questions=open_questions or [],
        approval_tier=approval_tier,
        excluded=excludes,
        sections=sections or {},
    )
