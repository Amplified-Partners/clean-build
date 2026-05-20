"""KaizenProposalGenerator — turns findings into proposals.

Reads 24h of findings, applies the deterministic rule book,
generates proposals, submits through the pipe, opens Linear
issues, schedules LoopClosers.

No LLM in the workflow body. Deterministic rule book only.
LLM-proposed interventions are v2 (with explicit INTUITED tier
and double-Council ratification).

Schedule: 06:00 UTC nightly.

Dana | 2026-05-20 | From Computer's Loom spec §5.3
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from loom.findings import Finding
from loom.proposals import Proposal
from loom.integrations.linear import LinearClient
from loom.integrations.pipe import PipeClient
from loom.integrations.vellum import VellumClient

log = logging.getLogger("loom.workflows.kaizen_generator")

SHEET_NAME = "kaizen-log"

# The rule book — deterministic, no LLM.
# Maps finding kind → proposal generation function.
# For findings without a rule: escalate to Council.
RULE_BOOK: dict[str, dict] = {
    "triangulation_drop": {
        "title": "Lower min-corroboration threshold for 7 days",
        "rationale": "Triangulation rate dropped below baseline. "
                     "Lower threshold temporarily to gather more data.",
        "intervention": {"action": "lower_corroboration_threshold", "delta": -1},
        "expected_metric": "tier_distribution",
        "observation_window_hours": 168,
        "reversible": True,
    },
    "contradiction_spike": {
        "title": "Council deliberation on top contradicting node pairs",
        "rationale": "Contradiction rate spiked above baseline. "
                     "Council should deliberate on the top contradicting pairs.",
        "intervention": {"action": "council_deliberation", "target": "contradictions"},
        "expected_metric": "tier_distribution",
        "observation_window_hours": 168,
        "reversible": True,
    },
    "provisional_backlog": {
        "title": "Trigger reprocess queue drain",
        "rationale": "Provisional entries exceeding threshold. "
                     "Drain the reprocess queue.",
        "intervention": {"action": "drain_reprocess_queue"},
        "expected_metric": "conversation_volume",
        "observation_window_hours": 48,
        "reversible": True,
    },
    "agent_silent": {
        "title": "Agent down — human review required",
        "rationale": "Agent has been silent beyond threshold. "
                     "No automatic intervention — humans decide.",
        "intervention": {"action": "human_review", "auto_intervene": False},
        "expected_metric": "agent_activity",
        "observation_window_hours": 24,
        "reversible": True,
    },
    "agent_drift": {
        "title": "Agent drift review — Council deliberation queued",
        "rationale": "Agent behaviour pattern has changed. "
                     "Council deliberation queued for review.",
        "intervention": {"action": "council_deliberation", "target": "agent_drift"},
        "expected_metric": "agent_activity",
        "observation_window_hours": 168,
        "reversible": True,
    },
    "budget_warning": {
        "title": "Budget review — vendor approaching cap",
        "rationale": "Vendor projected spend approaching monthly cap. "
                     "No automatic intervention — budget review required.",
        "intervention": {"action": "human_review", "auto_intervene": False},
        "expected_metric": "source_volume",
        "observation_window_hours": 168,
        "reversible": True,
    },
    "budget_critical": {
        "title": "Budget critical — halt non-essential agent workflows",
        "rationale": "Vendor projected to exceed monthly cap. "
                     "Halting non-essential workflows for this vendor.",
        "intervention": {"action": "halt_vendor_workflows"},
        "expected_metric": "source_volume",
        "observation_window_hours": 24,
        "reversible": True,
    },
}


def propose_for_finding(finding: Finding) -> Proposal | None:
    """Apply the deterministic rule book to a finding.

    Returns a Proposal if a rule matches, None otherwise.
    For findings without a rule: returns None (caller should
    escalate to Council).
    """
    rule = RULE_BOOK.get(finding.kind)
    if rule is None:
        return None

    return Proposal(
        title=rule["title"],
        rationale=rule["rationale"],
        evidence_finding_ids=[finding.id],
        intervention=rule["intervention"],
        reversible=rule.get("reversible", True),
        observation_window_hours=rule.get("observation_window_hours", 168),
        expected_metric=rule.get("expected_metric", ""),
        tier="STRUCTURED",  # Always. Never MEASURED.
        baseline_metric=finding.evidence,
    )


async def run_kaizen_generator(
    findings: list[Finding],
    vellum: VellumClient,
    pipe: PipeClient,
    linear: LinearClient,
) -> list[Proposal]:
    """Execute the KaizenProposalGenerator workflow.

    1. For each finding, generate a proposal if a rule matches
    2. Submit each proposal through the pipe
    3. Open a Linear issue for human visibility
    4. Witness the generator's own run
    """
    proposals: list[Proposal] = []
    novel_findings: list[Finding] = []

    for f in findings:
        proposal = propose_for_finding(f)
        if proposal:
            proposals.append(proposal)
        else:
            novel_findings.append(f)

    # Submit proposals through the pipe
    for p in proposals:
        submission_result = await pipe.submit(p.to_pipe_submission())

        # Open Linear issue for human visibility
        await linear.create_issue({
            "title": p.title,
            "body": (
                f"{p.rationale}\n\n"
                f"Witnessed: vellum://{submission_result['witness_id']}"
            ),
            "label": "kaizen-proposal",
            "metadata": {"proposal_id": p.id},
        })

        # Write proposal to Vellum
        await vellum.write_entry(SHEET_NAME, p.to_vellum_entry())

    # Novel findings → escalate to Council (write to kaizen-log)
    for f in novel_findings:
        await vellum.write_entry(SHEET_NAME, {
            "entry_type": "metric",
            "author": "loom.kaizen_generator",
            "content": f"novel finding — escalating to Council: {f.kind}",
            "epistemic_tier": "STRUCTURED",
            "metadata": {
                "finding_id": f.id,
                "finding_kind": f.kind,
                "action": "escalate_to_council",
            },
        })

    # Witness the generator's own run
    await vellum.write_entry(SHEET_NAME, {
        "entry_type": "metric",
        "author": "loom.kaizen_generator",
        "content": (
            f"generated {len(proposals)} proposals from "
            f"{len(findings)} findings"
        ),
        "epistemic_tier": "STRUCTURED",
        "metadata": {
            "proposal_count": len(proposals),
            "finding_count": len(findings),
            "novel_count": len(novel_findings),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    })

    log.info(
        "KaizenGenerator complete: %d proposals from %d findings (%d novel)",
        len(proposals), len(findings), len(novel_findings),
    )
    return proposals
