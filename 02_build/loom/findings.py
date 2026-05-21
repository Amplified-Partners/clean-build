"""Finding — the output of every health check.

Every health-check workflow produces zero or more findings.
Findings are tier-capped at STRUCTURED (heuristic observations,
not measured facts). Only the LoopCloser may promote to MEASURED
after evidence confirms a prediction.

Dana | 2026-05-20 | From Computer's Loom spec §4.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

Severity = Literal["info", "warning", "critical"]


@dataclass
class Finding:
    """A health-check observation, witnessed in Vellum."""

    id: str = field(default_factory=lambda: str(uuid4()))
    kind: str = ""  # e.g. "triangulation_drop", "agent_silent", "budget_warning"
    severity: Severity = "info"
    source_workflow: str = ""  # who found this
    evidence: dict = field(default_factory=dict)
    discovered_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    tier: str = "STRUCTURED"  # always; findings are heuristic
    related_entity_ids: list[str] = field(default_factory=list)

    def to_vellum_entry(self) -> dict:
        """Convert to a Vellum-compatible entry dict for witnessing."""
        return {
            "entry_type": "metric",
            "author": self.source_workflow,
            "content": f"{self.kind} ({self.severity})",
            "epistemic_tier": "STRUCTURED",
            "metadata": {
                "finding_id": self.id,
                "kind": self.kind,
                "severity": self.severity,
                "evidence": self.evidence,
                "related": self.related_entity_ids,
                "discovered_at": self.discovered_at.isoformat(),
            },
        }
