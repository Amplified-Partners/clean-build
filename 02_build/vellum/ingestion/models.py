"""Models for the Vellum Ingestion Gate.

Pure domain models. No I/O. Pydantic v2.

Writer types, proforma definitions, submissions, verdicts, signed records.
The proforma is the contract. The verdict is binary: ACCEPTED or REJECTED.

Devon-b5dc | 2026-05-14
"""

from __future__ import annotations

import enum
import hashlib
import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, Field

from vellum.gate.models import EpistemicStatus


# ---------------------------------------------------------------------------
# WriterType — who is trying to write to Vellum?
# Different writers have different proformas.
# ---------------------------------------------------------------------------


class WriterType(str, enum.Enum):
    """Classification of who is submitting to Vellum.

    Each writer type has a different proforma (different required fields,
    different epistemic tier ceilings, different signature requirements).
    """

    AGENT = "AGENT"             # Devon, Cassian, Antigravity, any AI agent
    HUMAN = "HUMAN"             # Ewan or other human operator
    TOOL = "TOOL"               # Linear, GitHub, Motion, Figma — tool reports
    RESEARCH = "RESEARCH"       # Perplexity, SearXNG — research findings
    SENSOR = "SENSOR"           # Automated telemetry, metrics, health checks
    ORCHESTRATOR = "ORCHESTRATOR"  # Cove, Temporal — workflow completions


# ---------------------------------------------------------------------------
# ProformaField — one required field in a proforma.
# ---------------------------------------------------------------------------


class ProformaField(BaseModel):
    """A single field requirement in a proforma.

    Defines: what must be present, what type, whether optional,
    and what constraints apply.
    """

    name: str
    field_type: Literal["str", "int", "float", "bool", "datetime", "list", "dict"]
    required: bool = True
    max_length: int | None = None
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: list[str] | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# Proforma — the contract a submission must satisfy.
# ---------------------------------------------------------------------------


class Proforma(BaseModel):
    """A proforma defines what a submission MUST contain to pass the gate.

    Different writer types have different proformas. The proforma is code,
    not policy. It cannot be "interpreted." It either passes or it doesn't.
    """

    proforma_id: str
    writer_type: WriterType
    record_type: str = Field(description="What kind of record (e.g. 'completion_report', 'research_finding', 'plan', 'decision', 'telemetry')")
    fields: list[ProformaField]
    max_epistemic_tier: EpistemicStatus = Field(
        default=EpistemicStatus.STRUCTURED,
        description="Ceiling tier this writer/record type can claim. An agent cannot claim PROVEN.",
    )
    requires_signature: bool = True
    requires_provenance: bool = True
    requires_work_packet_id: bool = False
    description: str = ""


# ---------------------------------------------------------------------------
# Submission — the raw thing hitting the gate.
# Untrusted until validated.
# ---------------------------------------------------------------------------


class Submission(BaseModel):
    """A raw submission to the ingestion gate.

    This is untrusted. It claims things. The gate verifies those claims.
    """

    submission_id: str
    writer_type: WriterType
    record_type: str
    submitted_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    claimed_epistemic_tier: EpistemicStatus
    author: str = Field(description="Who is submitting (agent name, human name, tool ID)")
    session_id: str | None = None
    work_packet_id: str | None = None
    provenance: str | None = Field(default=None, description="Where did this come from? Source reference.")
    payload: dict[str, Any] = Field(default_factory=dict, description="The actual data being submitted.")
    signature: str | None = Field(default=None, description="Author signature (agent name + date + session ID)")


# ---------------------------------------------------------------------------
# GateVerdict — the output of the ingestion gate. Binary.
# ---------------------------------------------------------------------------


class GateVerdict(BaseModel):
    """The gate's verdict on a submission.

    ACCEPTED or REJECTED. Nothing in between.
    Every rejection carries reason codes — explicit, machine-readable.
    """

    submission_id: str
    decision: Literal["ACCEPTED", "REJECTED"]
    reason_codes: list[str] = Field(default_factory=list)
    effective_tier: EpistemicStatus = Field(
        description="The tier actually assigned (may be lower than claimed, via min-rule)"
    )
    evaluated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    gate_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# SignedRecord — what gets stored in Vellum after passing the gate.
# Immutable. Hash-chained. Attributed.
# ---------------------------------------------------------------------------


class SignedRecord(BaseModel):
    """A record that has passed the gate and been signed by Vellum.

    This is the unit of storage. It is:
    - Immutable (frozen after creation)
    - Hash-chained (each record includes hash of previous)
    - Attributed (author, timestamp, session, provenance)
    - Tiered (epistemic status assigned by the gate, not claimed by the writer)
    """

    record_id: str
    submission_id: str
    writer_type: WriterType
    record_type: str
    author: str
    session_id: str | None
    work_packet_id: str | None
    provenance: str | None
    payload: dict[str, Any]
    assigned_tier: EpistemicStatus = Field(
        description="Tier assigned by the gate (never higher than proforma ceiling)"
    )
    signed_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    previous_hash: str = Field(description="SHA-256 of previous record — hash chain")
    record_hash: str = Field(description="SHA-256 of this record's content")
    gate_version: str = "1.0.0"

    @staticmethod
    def compute_hash(
        submission_id: str,
        record_type: str,
        author: str,
        payload: dict[str, Any],
        assigned_tier: EpistemicStatus,
        previous_hash: str,
        signed_at: dt.datetime,
    ) -> str:
        """Deterministic hash of record content. Cannot be forged."""
        content = (
            f"{submission_id}|{record_type}|{author}|"
            f"{sorted(payload.items())}|{assigned_tier.value}|"
            f"{previous_hash}|{signed_at.isoformat()}"
        )
        return hashlib.sha256(content.encode()).hexdigest()
