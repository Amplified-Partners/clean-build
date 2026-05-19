"""Portable spine — full Amplified Weight shape.

The spine has four components:
  1. Epistemic core (the Python) — Layer 0 invariant, the steady stomach
  2. Five Rods — radical honesty, transparency, attribution, win-win, idea meritocracy
  3. The Amplified Weight — the Brain schema (RawRecord → KnowledgeUnit →
     LiftCandidate → ResearchJob → LiftResult → PortableSpine → AgentWriteback)
  4. Portable brain — task-specific context in, learning out

Prior art: brain_schema.py (Ewan, 2026-05-19) — the canonical shapes
for the full pipe. This module governs the portable spine and agent
writeback models. The LiftResult and ResearchJob shapes live in
research_pipe/models.py.

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from epistemic_core.tiers import EpistemicTier


# ---------------------------------------------------------------------------
# Modality — how was this captured?
# ---------------------------------------------------------------------------


class Modality(str, enum.Enum):
    """Source modality for raw records entering the Brain."""

    VOICE = "voice"
    THREAD = "thread"
    METRIC = "metric"
    CUSTOMER_MESSAGE = "customer_message"
    STAFF_NOTE = "staff_note"
    REVIEW = "review"
    ISSUE = "issue"
    AI_DRAFT = "ai_draft"
    WEB = "web"
    GITHUB = "github"
    HUMAN = "human"


# ---------------------------------------------------------------------------
# Permitted use — what may consumers do with this unit?
# ---------------------------------------------------------------------------


class PermittedUse(str, enum.Enum):
    """Governs what downstream consumers may do with a KnowledgeUnit."""

    CONTENT_CREATION = "content_creation"
    VOICE_PRESERVATION = "voice_preservation"
    DOCTRINE_SEED = "doctrine_seed"
    CLIENT_VALUE_SURFACE = "client_value_surface"
    AGENT_PROMPT_SEED = "agent_prompt_seed"
    OPERATIONAL_TRUTH = "operational_truth"
    FACTUAL_CLAIM = "factual_claim_without_evidence"


# ---------------------------------------------------------------------------
# Layer 1: RawRecord (immutable capture)
# ---------------------------------------------------------------------------


class RawRecord(BaseModel):
    """Immutable raw record from source ingestion.

    Everything entering the Brain starts here. Content hash provides
    deduplication. Boundary policy defaults to anonymise.
    """

    record_id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: Modality
    source_ref: str
    content: str
    content_hash: str
    actor: str
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    boundary_policy: str = "anonymise_where_feasible"


# ---------------------------------------------------------------------------
# Layers 2-3: KnowledgeUnit (parsed, classified, tiered)
# ---------------------------------------------------------------------------


class KnowledgeUnit(BaseModel):
    """A semantic unit extracted from raw records, tiered and labelled.

    Carries its epistemic tier, permitted uses, and full attribution chain.
    """

    unit_id: str = Field(default_factory=lambda: str(uuid4()))
    packet_type: str  # e.g. 'opinion', 'explanation', 'story', 'method'
    content: str
    epistemic_tier: EpistemicTier
    source_record_ids: list[str]
    permitted_use: list[PermittedUse] = Field(default_factory=list)
    not_for: list[PermittedUse] = Field(default_factory=list)
    attribution_originated_by: list[str] = Field(default_factory=list)
    attribution_crystallised_by: list[str] = Field(default_factory=list)
    transformation_history: list[str] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    valid_until: datetime | None = None


# ---------------------------------------------------------------------------
# Layer 4: LiftCandidate (research lift queue entry)
# ---------------------------------------------------------------------------


class LiftCandidate(BaseModel):
    """An INTUITED or STRUCTURED unit identified as having operational potential.

    Scored on three axes: business value, agent reuse, risk if wrong.
    Routes into the ResearchJob pipeline.
    """

    candidate_id: str = Field(default_factory=lambda: str(uuid4()))
    knowledge_unit_id: str
    candidate_type: str  # e.g. 'method_hypothesis', 'process_improvement'
    current_tier: EpistemicTier
    target_claim_or_gap: str
    business_value_score: int = Field(ge=1, le=5)
    agent_reuse_score: int = Field(ge=1, le=5)
    risk_if_wrong_score: int = Field(ge=1, le=5)
    recommended_route: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Spine context — what the agent sees
# ---------------------------------------------------------------------------


class SpineContext(BaseModel):
    """Curated context bundle delivered to an agent.

    brain_facts: governed facts from brain_curator packets
    github_state: relevant repo/PR/issue state
    decisions: prior decisions relevant to the task
    """

    brain_facts: list[dict[str, Any]] = Field(default_factory=list)
    github_state: dict[str, Any] = Field(default_factory=dict)
    decisions: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# PortableSpine — task-specific context for an agent
# ---------------------------------------------------------------------------


DEFAULT_EXCLUDES: list[str] = [
    "raw_transcript",
    "stale_packets",
    "unscoped_opinions",
    "direct_crm_records",
]


class PortableSpine(BaseModel):
    """A curated, task-specific bundle of context given to an agent before action.

    Explicit about what it includes AND what it omits.
    Carries a minimum_tier_required — the agent cannot operate on data
    below this tier without flagging.

    The four components:
      1. Epistemic core (the Python) — enforced by minimum_tier_required
      2. Five Rods — enforced by constraints list
      3. Amplified Weight — the full Brain schema pipe
      4. Portable brain — this model + AgentWriteback
    """

    spine_id: str = Field(default_factory=lambda: str(uuid4()))
    problem_id: str
    task_summary: str
    agent_role_target: str
    approval_tier_required: int = 1
    minimum_tier_required: EpistemicTier = EpistemicTier.STRUCTURED

    # What the agent may use
    allowed_intuited_inputs: list[str] = Field(default_factory=list)
    context: SpineContext = Field(default_factory=SpineContext)
    allowed_tools: list[str] = Field(default_factory=list)
    disallowed_tools: list[str] = Field(default_factory=list)

    # Handoff
    handoff_prompt: str = ""

    # Explicit excludes (documented omissions)
    excluded: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)

    # Lifecycle
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    valid_until: datetime | None = None

    @property
    def is_expired(self) -> bool:
        if self.valid_until is None:
            return False
        return datetime.now(timezone.utc) > self.valid_until


# ---------------------------------------------------------------------------
# AgentWriteback — the learning loop
# ---------------------------------------------------------------------------


class AgentWriteback(BaseModel):
    """The learning and outcome record written back to the Brain post-task.

    Closes the compound engineering loop:
      PortableSpine → agent work → AgentWriteback → Brain.

    The writeback feeds the Plan-Execution Mirror — plan vs actual,
    spine effectiveness, reusable patterns, mistakes avoided.
    """

    writeback_id: str = Field(default_factory=lambda: str(uuid4()))
    spine_id: str
    agent_id: str
    status: str  # success, failed, parked
    what_changed: list[str] = Field(default_factory=list)
    decisions_made: list[str] = Field(default_factory=list)
    reusable_patterns: list[str] = Field(default_factory=list)
    mistakes_avoided: list[str] = Field(default_factory=list)
    spine_effectiveness_note: str = ""
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Generator — build a spine for a task
# ---------------------------------------------------------------------------


def generate_spine(
    *,
    problem_id: str,
    task_summary: str,
    agent_role_target: str,
    context: SpineContext | None = None,
    minimum_tier_required: EpistemicTier = EpistemicTier.STRUCTURED,
    allowed_tools: list[str] | None = None,
    disallowed_tools: list[str] | None = None,
    constraints: list[str] | None = None,
    handoff_prompt: str = "",
    ttl: timedelta = timedelta(hours=24),
    extra_excludes: list[str] | None = None,
) -> PortableSpine:
    """Generate a portable spine with explicit includes and excludes.

    The spine is valid for `ttl` from generation time. Constraints default
    to the Five Rods.
    """
    excludes = list(DEFAULT_EXCLUDES)
    if extra_excludes:
        excludes.extend(extra_excludes)

    default_constraints = [
        "radical_honesty",
        "radical_transparency",
        "radical_attribution",
        "win_win",
        "idea_meritocracy",
    ]
    applied_constraints = (constraints or []) + default_constraints

    return PortableSpine(
        problem_id=problem_id,
        task_summary=task_summary,
        agent_role_target=agent_role_target,
        minimum_tier_required=minimum_tier_required,
        context=context or SpineContext(),
        allowed_tools=allowed_tools or [],
        disallowed_tools=disallowed_tools or [],
        constraints=applied_constraints,
        handoff_prompt=handoff_prompt,
        excluded=excludes,
        valid_until=datetime.now(timezone.utc) + ttl,
    )
