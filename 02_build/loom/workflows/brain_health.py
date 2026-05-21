"""BrainHealthCheck — nightly health check on the Brain.

Reads DuckDB metrics, compares to baselines, writes findings
to Vellum, alerts on critical. Always writes a run-summary
so silence is a signal.

Schedule: 03:30 UTC nightly (after DuckDB snapshot at 03:00).

Dana | 2026-05-20 | From Computer's Loom spec §5.1
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from loom.findings import Finding
from loom.integrations.dq import DqClient
from loom.integrations.telegram import TelegramClient
from loom.integrations.vellum import VellumClient

log = logging.getLogger("loom.workflows.brain_health")

SHEET_NAME = "brain-health"


async def run_brain_health_check(
    vellum: VellumClient,
    dq: DqClient,
    telegram: TelegramClient,
) -> list[Finding]:
    """Execute the BrainHealthCheck workflow.

    1. Read DuckDB metrics
    2. Compare to baselines
    3. Write findings + alert if critical
    4. Always write a run-summary (silence is a signal)
    """
    # 1. Read metrics
    tier_data = await dq.run("tier_distribution", executed_by="loom.brain_health")
    agent_data = await dq.run("agent_activity", executed_by="loom.brain_health")

    # 2. Load baselines from previous runs
    baselines = await vellum.load_baselines(SHEET_NAME)

    # 3. Evaluate findings
    findings: list[Finding] = []

    # Check tier distribution — if INTUITED entries dominate, corroboration is dropping
    if tier_data.get("rows"):
        tier_map = {}
        for row in tier_data["rows"]:
            if len(row) >= 2:
                tier_map[row[0]] = row[1]
        intuited = tier_map.get("INTUITED", 0)
        structured = tier_map.get("STRUCTURED", 0)
        total = intuited + structured
        if total > 0:
            corroboration_rate = structured / total
            baseline_rate = baselines.get("triangulation", 0.8)
            if corroboration_rate < baseline_rate * 0.9:
                findings.append(Finding(
                    kind="triangulation_drop",
                    severity="warning",
                    source_workflow="loom.brain_health",
                    evidence={
                        "latest_rate": round(corroboration_rate, 4),
                        "baseline_rate": baseline_rate,
                        "ratio": round(corroboration_rate / baseline_rate, 4) if baseline_rate else 0,
                        "intuited_count": intuited,
                        "structured_count": structured,
                    },
                ))

    # Check agent activity — detect any agents with zero recent entries
    if agent_data.get("rows"):
        active_agents = {row[0] for row in agent_data["rows"] if len(row) >= 1}
        if len(active_agents) == 0:
            findings.append(Finding(
                kind="no_active_agents",
                severity="critical",
                source_workflow="loom.brain_health",
                evidence={"agent_count": 0},
            ))

    # 4. Write findings to Vellum + alert if critical
    for f in findings:
        await vellum.write_entry(SHEET_NAME, f.to_vellum_entry())
        if f.severity == "critical":
            await telegram.alert(
                f"BRAIN CRITICAL: {f.kind}",
                f.evidence,
            )

    # 5. Always write a run-summary so silence is a signal
    await vellum.write_entry(SHEET_NAME, {
        "entry_type": "health_check",
        "author": "loom.brain_health",
        "content": f"check complete: {len(findings)} findings",
        "epistemic_tier": "STRUCTURED",
        "metadata": {
            "finding_count": len(findings),
            "finding_kinds": [f.kind for f in findings],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    })

    log.info("BrainHealthCheck complete: %d findings", len(findings))
    return findings
