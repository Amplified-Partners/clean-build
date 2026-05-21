"""Conversation participant — who can speak on a correspondence sheet.

Participants have an identity, a type (human/agent/model), a role
(owner/participant/observer), and a max epistemic tier ceiling.
The min-rule applies: a model cannot claim a tier above its ceiling,
and the conversation's effective tier is min(all participant tiers).

Human speech is always INTUITED. Agent structured output caps at
STRUCTURED. Only measurement pipelines can claim MEASURED.

Dana | 2026-05-20 | Correspondence mode — participant model
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

ParticipantType = Literal["human", "agent", "model"]
ParticipantRole = Literal["owner", "participant", "observer"]
EpistemicTier = Literal["INTUITED", "STRUCTURED", "MEASURED", "PROVEN"]

# Tier ceiling by participant type — the min-rule at the identity boundary
TIER_CEILING: dict[str, str] = {
    "human": "INTUITED",      # Human speech is always INTUITED
    "agent": "STRUCTURED",    # Agent output is STRUCTURED at best
    "model": "STRUCTURED",    # Model output is STRUCTURED at best
}

# Ordered for comparison
_TIER_ORDER = {"INTUITED": 0, "STRUCTURED": 1, "MEASURED": 2, "PROVEN": 3}


def tier_min(a: str, b: str) -> str:
    """Return the lower of two epistemic tiers. The min-rule."""
    return a if _TIER_ORDER.get(a, 0) <= _TIER_ORDER.get(b, 0) else b


class Participant(BaseModel):
    """A participant in a correspondence conversation.

    Tracks identity, type, role, and epistemic tier ceiling.
    The ceiling enforces the min-rule: no participant can claim
    a tier above what their type permits.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    sheet_id: str
    identity: str  # e.g. "ewan", "antigravity", "devon-9892", "gpt-5.5"
    display_name: str = ""
    participant_type: ParticipantType = "agent"
    role: ParticipantRole = "participant"
    max_tier: EpistemicTier = "STRUCTURED"
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True

    def model_post_init(self, __context: object) -> None:
        if not self.display_name:
            self.display_name = self.identity
        # Enforce tier ceiling by participant type
        ceiling = TIER_CEILING.get(self.participant_type, "INTUITED")
        self.max_tier = tier_min(self.max_tier, ceiling)
