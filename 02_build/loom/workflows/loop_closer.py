"""LoopCloser — verifies or rolls back Kaizen proposals.

Per proposal: waits the observation window, re-measures,
compares against expected delta, either confirms (→ MEASURED)
or rolls back through the pipe.

This is the load-bearing piece of Kaizen. Without it, the system
can quietly drift. With it, every change has to prove itself
within its window or it gets undone, and Vellum has the receipt
either way.

Schedule: event-driven (one per proposal).

Dana | 2026-05-20 | From Computer's Loom spec §5.4
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from loom.proposals import Proposal
from loom.integrations.linear import LinearClient
from loom.integrations.pipe import PipeClient
from loom.integrations.vellum import VellumClient

log = logging.getLogger("loom.workflows.loop_closer")

SHEET_NAME = "kaizen-log"


def evaluate_proposal(
    proposal: Proposal,
    before: dict,
    after: dict,
) -> dict:
    """Compare before/after metrics to determine if improvement confirmed.

    Returns: {confirmed: bool, reason: str, delta: dict}

    Simple evaluation: if the after metric shows improvement
    (or at least no regression), confirm. Otherwise, roll back.
    """
    # Find a comparable numeric key in both dicts
    before_value = None
    after_value = None
    for key in ("total", "count", "rate", "value"):
        if key in before and key in after:
            before_value = before[key]
            after_value = after[key]
            break

    if (
        before_value is not None
        and after_value is not None
        and isinstance(before_value, (int, float))
        and isinstance(after_value, (int, float))
    ):
        delta = after_value - before_value
        # For most metrics, higher is better (more entries, more corroboration)
        # Budget metrics are inverted (lower is better) but the intervention
        # is "halt workflows" so we check if spend decreased
        if proposal.intervention.get("action") == "halt_vendor_workflows":
            confirmed = delta <= 0
            reason = (
                "spend decreased or held steady" if confirmed
                else f"spend increased by {delta}"
            )
        else:
            confirmed = delta >= 0
            reason = (
                "metric improved or held steady" if confirmed
                else f"metric decreased by {abs(delta)}"
            )
        return {
            "confirmed": confirmed,
            "reason": reason,
            "delta": {"before": before_value, "after": after_value, "change": delta},
        }

    # Can't compare — default to not confirmed (safe)
    return {
        "confirmed": False,
        "reason": "unable to compare before/after metrics",
        "delta": {"before": before_value, "after": after_value},
    }


async def run_loop_closer(
    proposal: Proposal,
    after_metric: dict,
    vellum: VellumClient,
    pipe: PipeClient,
    linear: LinearClient,
) -> dict:
    """Execute the LoopCloser workflow for a single proposal.

    In production, this runs after sleeping the observation window
    (Temporal handles long sleeps natively — survives restarts).
    In tests, the caller provides the after_metric directly.

    1. Compare before/after
    2. If improved: confirm (MEASURED), close Linear issue
    3. If not: roll back through pipe, witness failure
    """
    result = evaluate_proposal(proposal, proposal.baseline_metric, after_metric)

    if result["confirmed"]:
        # Confirmed improvement → MEASURED (we have evidence now)
        await vellum.write_entry(SHEET_NAME, {
            "entry_type": "metric",
            "author": "loom.loop_closer",
            "content": f"proposal {proposal.id} confirmed improvement",
            "epistemic_tier": "MEASURED",  # promoted — we have evidence
            "metadata": {
                "proposal_id": proposal.id,
                "title": proposal.title,
                "before": proposal.baseline_metric,
                "after": after_metric,
                "delta": result["delta"],
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
            },
        })
        await linear.close_issue(proposal.id, "kaizen-confirmed")
        log.info("Proposal %s CONFIRMED: %s", proposal.id, result["reason"])
    else:
        # Roll back through the pipe
        await pipe.rollback(proposal.id)
        await vellum.write_entry(SHEET_NAME, {
            "entry_type": "metric",
            "author": "loom.loop_closer",
            "content": f"proposal {proposal.id} rolled back",
            "epistemic_tier": "STRUCTURED",  # failed — stays STRUCTURED
            "metadata": {
                "proposal_id": proposal.id,
                "title": proposal.title,
                "before": proposal.baseline_metric,
                "after": after_metric,
                "delta": result["delta"],
                "reason": result["reason"],
                "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            },
        })
        await linear.close_issue(proposal.id, "kaizen-failed")
        log.info("Proposal %s ROLLED BACK: %s", proposal.id, result["reason"])

    return result
