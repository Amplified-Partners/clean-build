"""Proforma Registry — the book of rules for what gets in.

Each writer type + record type combination has exactly one proforma.
The proforma defines the contract. If there's no proforma registered,
the submission is rejected — unknown combinations don't pass.

Devon-b5dc | 2026-05-14
"""

from __future__ import annotations

from vellum.gate.models import EpistemicStatus
from vellum.ingestion.models import (
    Proforma,
    ProformaField,
    WriterType,
)


class ProformaRegistry:
    """Registry of proformas. One proforma per (writer_type, record_type) pair.

    If a submission arrives with an unregistered combination, it's rejected.
    No exceptions. No "close enough." No fallback proformas.
    """

    def __init__(self) -> None:
        self._registry: dict[tuple[WriterType, str], Proforma] = {}

    def register(self, proforma: Proforma) -> None:
        """Register a proforma. Overwrites if already present."""
        key = (proforma.writer_type, proforma.record_type)
        self._registry[key] = proforma

    def get(self, writer_type: WriterType, record_type: str) -> Proforma | None:
        """Look up the proforma for a given writer + record type. None if unregistered."""
        return self._registry.get((writer_type, record_type))

    def registered_types(self) -> list[tuple[WriterType, str]]:
        """List all registered (writer_type, record_type) pairs."""
        return list(self._registry.keys())

    def __len__(self) -> int:
        return len(self._registry)


# ---------------------------------------------------------------------------
# Default proformas — the minimum set Vellum ships with.
# These define what each writer type must provide for common record types.
# ---------------------------------------------------------------------------


def build_default_registry() -> ProformaRegistry:
    """Build the default proforma registry.

    This is the minimum viable set of gates. Each one defines
    exactly what is required. No ambiguity.
    """
    registry = ProformaRegistry()

    # --- AGENT proformas ---

    registry.register(Proforma(
        proforma_id="agent.completion_report",
        writer_type=WriterType.AGENT,
        record_type="completion_report",
        max_epistemic_tier=EpistemicStatus.STRUCTURED,
        requires_work_packet_id=True,
        description="Agent reporting completion of a task.",
        fields=[
            ProformaField(name="task_id", field_type="str", required=True, description="Linear/internal task ID"),
            ProformaField(name="summary", field_type="str", required=True, max_length=2000, description="What was done"),
            ProformaField(name="artefacts", field_type="list", required=True, description="Links to PRs, files, outputs"),
            ProformaField(name="tests_passed", field_type="bool", required=True, description="Did tests pass?"),
            ProformaField(name="unresolved_risks", field_type="list", required=False, description="Known risks or gaps"),
        ],
    ))

    registry.register(Proforma(
        proforma_id="agent.observation",
        writer_type=WriterType.AGENT,
        record_type="observation",
        max_epistemic_tier=EpistemicStatus.STRUCTURED,
        requires_work_packet_id=False,
        description="Agent reporting something it noticed (drift, anomaly, pattern).",
        fields=[
            ProformaField(name="observation", field_type="str", required=True, max_length=2000, description="What was observed"),
            ProformaField(name="severity", field_type="str", required=True, allowed_values=["info", "warning", "critical"], description="How severe"),
            ProformaField(name="evidence", field_type="str", required=False, description="Supporting evidence or reference"),
        ],
    ))

    # --- HUMAN proformas ---

    registry.register(Proforma(
        proforma_id="human.decision",
        writer_type=WriterType.HUMAN,
        record_type="decision",
        max_epistemic_tier=EpistemicStatus.STRUCTURED,
        requires_work_packet_id=False,
        description="Human making a decision (approval, direction, correction).",
        fields=[
            ProformaField(name="decision", field_type="str", required=True, max_length=2000, description="The decision made"),
            ProformaField(name="context", field_type="str", required=False, max_length=5000, description="Why this decision was made"),
            ProformaField(name="reversible", field_type="bool", required=True, description="Is this reversible?"),
        ],
    ))

    registry.register(Proforma(
        proforma_id="human.plan",
        writer_type=WriterType.HUMAN,
        record_type="plan",
        max_epistemic_tier=EpistemicStatus.STRUCTURED,
        requires_work_packet_id=False,
        description="Human verbal plan captured and structured.",
        fields=[
            ProformaField(name="intent", field_type="str", required=True, max_length=5000, description="What is the desired outcome"),
            ProformaField(name="constraints", field_type="list", required=False, description="Rules bounding the work"),
            ProformaField(name="delegation_boundary", field_type="str", required=True, allowed_values=["suggest_only", "draft", "execute"], description="How much autonomy"),
        ],
    ))

    # --- TOOL proformas ---

    registry.register(Proforma(
        proforma_id="tool.status_update",
        writer_type=WriterType.TOOL,
        record_type="status_update",
        max_epistemic_tier=EpistemicStatus.STRUCTURED,
        requires_work_packet_id=True,
        description="Tool reporting status change (Linear, GitHub, etc).",
        fields=[
            ProformaField(name="tool_name", field_type="str", required=True, description="Which tool"),
            ProformaField(name="entity_id", field_type="str", required=True, description="Tool-internal entity ID"),
            ProformaField(name="previous_status", field_type="str", required=False, description="What it was"),
            ProformaField(name="new_status", field_type="str", required=True, description="What it is now"),
            ProformaField(name="changed_at", field_type="datetime", required=True, description="When the change happened"),
        ],
    ))

    # --- RESEARCH proformas ---

    registry.register(Proforma(
        proforma_id="research.finding",
        writer_type=WriterType.RESEARCH,
        record_type="finding",
        max_epistemic_tier=EpistemicStatus.STRUCTURED,
        requires_work_packet_id=False,
        description="Research finding (Perplexity, SearXNG, literature).",
        fields=[
            ProformaField(name="question", field_type="str", required=True, max_length=1000, description="What was being researched"),
            ProformaField(name="finding", field_type="str", required=True, max_length=5000, description="What was found"),
            ProformaField(name="sources", field_type="list", required=True, description="Source URLs or references"),
            ProformaField(name="confidence", field_type="float", required=True, min_value=0.0, max_value=1.0, description="Confidence in finding"),
        ],
    ))

    # --- SENSOR proformas ---

    registry.register(Proforma(
        proforma_id="sensor.telemetry",
        writer_type=WriterType.SENSOR,
        record_type="telemetry",
        max_epistemic_tier=EpistemicStatus.MEASURED,
        requires_signature=False,
        requires_work_packet_id=False,
        description="Automated measurement (performance, health, usage).",
        fields=[
            ProformaField(name="metric_name", field_type="str", required=True, description="What is being measured"),
            ProformaField(name="value", field_type="float", required=True, description="The measurement"),
            ProformaField(name="unit", field_type="str", required=True, description="Unit of measurement"),
            ProformaField(name="measured_at", field_type="datetime", required=True, description="When measured"),
            ProformaField(name="source_system", field_type="str", required=True, description="What system produced this"),
        ],
    ))

    # --- ORCHESTRATOR proformas ---

    registry.register(Proforma(
        proforma_id="orchestrator.workflow_result",
        writer_type=WriterType.ORCHESTRATOR,
        record_type="workflow_result",
        max_epistemic_tier=EpistemicStatus.STRUCTURED,
        requires_work_packet_id=True,
        description="Orchestrator reporting workflow completion.",
        fields=[
            ProformaField(name="workflow_id", field_type="str", required=True, description="Temporal/Cove workflow ID"),
            ProformaField(name="status", field_type="str", required=True, allowed_values=["completed", "failed", "cancelled", "timed_out"], description="Outcome"),
            ProformaField(name="outputs", field_type="list", required=True, description="What was produced"),
            ProformaField(name="duration_seconds", field_type="float", required=True, min_value=0.0, description="How long it took"),
            ProformaField(name="failures", field_type="list", required=False, description="What went wrong, if anything"),
        ],
    ))

    return registry
