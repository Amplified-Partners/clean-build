"""Proposal — the output of the Kaizen generator.

Every outcome the loom wants to enact is a proposal, submitted
through the pipe. Proposals are tier-capped at STRUCTURED. They're
heuristic interventions, not measured facts. They become MEASURED
only if the LoopCloser verifies the predicted improvement.

Dana | 2026-05-20 | From Computer's Loom spec §4.2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class Proposal:
    """A Kaizen intervention, submitted through the pipe."""

    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    rationale: str = ""
    evidence_finding_ids: list[str] = field(default_factory=list)
    intervention: dict = field(default_factory=dict)  # what to actually do
    reversible: bool = True
    observation_window_hours: int = 168  # default 7 days
    expected_metric: str = ""  # named DuckDB query
    expected_delta: dict = field(default_factory=dict)  # baseline vs target
    tier: str = "STRUCTURED"  # always; proposals are heuristic
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    baseline_metric: dict = field(default_factory=dict)

    def to_pipe_submission(self) -> dict:
        """Convert to a pipe submission dict."""
        return {
            "kind": "meta_change",
            "payload": self.intervention,
            "attributed_to": "loom.kaizen_generator",
            "tier": self.tier,
            "evidence_refs": self.evidence_finding_ids,
            "rollback_plan": {
                "reversible": self.reversible,
                "window_hours": self.observation_window_hours,
            },
        }

    def to_vellum_entry(self) -> dict:
        """Convert to a Vellum-compatible entry dict for witnessing."""
        return {
            "entry_type": "metric",
            "author": "loom.kaizen_generator",
            "content": f"proposal: {self.title}",
            "epistemic_tier": "STRUCTURED",
            "metadata": {
                "proposal_id": self.id,
                "title": self.title,
                "rationale": self.rationale,
                "evidence_finding_ids": self.evidence_finding_ids,
                "reversible": self.reversible,
                "observation_window_hours": self.observation_window_hours,
                "expected_metric": self.expected_metric,
            },
        }
