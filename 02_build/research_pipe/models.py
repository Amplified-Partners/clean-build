"""Research pipe domain models.

Tracks the lifecycle of a research job from intake through closure.
Every claim must link to evidence. Every job must close with proof
of what happened — not just "research done".

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from epistemic_core.tiers import EpistemicTier


# ---------------------------------------------------------------------------
# Research job states
# ---------------------------------------------------------------------------

ResearchJobState = Literal[
    "intake_open",
    "research_running",
    "research_done_implementation_pending",
    "implemented_verified",
    "parked_verified",
    "rejected_verified",
    "no_action_verified",
]

TERMINAL_STATES: frozenset[str] = frozenset({
    "implemented_verified",
    "parked_verified",
    "rejected_verified",
    "no_action_verified",
})


# ---------------------------------------------------------------------------
# Evidence item
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    """A piece of evidence supporting or refuting a research claim."""

    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    source: str
    content: str
    epistemic_tier: EpistemicTier = EpistemicTier.INTUITED
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Research question
# ---------------------------------------------------------------------------


class ResearchQuestion(BaseModel):
    """A specific question within a research job."""

    question_id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    answer: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["open", "answered", "inconclusive"] = "open"


# ---------------------------------------------------------------------------
# Claim-evidence link
# ---------------------------------------------------------------------------


class ClaimEvidenceLink(BaseModel):
    """Links a claim to its supporting/refuting evidence."""

    link_id: str = Field(default_factory=lambda: str(uuid4()))
    claim: str
    evidence_id: str
    relationship: Literal["supports", "refutes", "neutral"] = "supports"
    strength: float = 0.5


# ---------------------------------------------------------------------------
# Lift result (closure evidence)
# ---------------------------------------------------------------------------


class LiftResult(BaseModel):
    """Closure evidence for a research job.

    Without a LiftResult, a job cannot move to a terminal state.
    """

    result_id: str = Field(default_factory=lambda: str(uuid4()))
    outcome: Literal[
        "implemented", "parked", "rejected", "no_action",
    ]
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    decided_by: str = ""
    decided_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Research job
# ---------------------------------------------------------------------------


class ResearchJob(BaseModel):
    """A research job tracking from intake to verified closure."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    state: ResearchJobState = "intake_open"
    questions: list[ResearchQuestion] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    claim_links: list[ClaimEvidenceLink] = Field(default_factory=list)
    lift_result: LiftResult | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
