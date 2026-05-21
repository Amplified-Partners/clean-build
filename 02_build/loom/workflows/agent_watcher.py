"""AgentWatcher — monitors every registered agent.

Polls each agent for liveness, emits telemetry to their
correspondence sheet, flags silence and drift findings.
Session-bound agents (Perplexity) don't trigger silence warnings.

Schedule: every 15 minutes.

Dana | 2026-05-20 | From Computer's Loom spec §5.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from loom.config import AgentRecord
from loom.findings import Finding
from loom.integrations.telegram import TelegramClient
from loom.integrations.vellum import VellumClient

log = logging.getLogger("loom.workflows.agent_watcher")

FLEET_SHEET = "agent-fleet"


async def check_agent_liveness(
    agent: AgentRecord,
    vellum: VellumClient,
) -> dict:
    """Determine liveness signal for an agent.

    - If output_surface == vellum: check last Vellum write
    - If output_surface == github_prs: would check last commit (stubbed)
    - If session-bound (no expected_heartbeat): always considered alive

    Returns: {kind, last_signal_at, minutes_since_last_signal}
    """
    now = datetime.now(timezone.utc)

    # Session-bound agents have no expected cadence
    if agent.expected_heartbeat_minutes is None:
        return {
            "kind": "session-bound",
            "last_signal_at": now.isoformat(),
            "minutes_since_last_signal": 0,
        }

    # Check Vellum for recent entries by this agent
    if agent.output_surface == "vellum":
        entries = await vellum.read_recent_entries(
            agent.correspondence_sheet, hours=24
        )
        agent_entries = [
            e for e in entries if e.get("author", "").startswith(agent.id)
        ]
        if agent_entries:
            last = agent_entries[-1]
            last_at = datetime.fromisoformat(last["timestamp"])
            minutes = (now - last_at).total_seconds() / 60
            return {
                "kind": "vellum",
                "last_signal_at": last["timestamp"],
                "minutes_since_last_signal": int(minutes),
            }

    # Default: no signal found — report silence
    return {
        "kind": "no_signal",
        "last_signal_at": None,
        "minutes_since_last_signal": 9999,
    }


async def summarise_recent_output(
    agent: AgentRecord,
    vellum: VellumClient,
    hours: int = 1,
) -> dict:
    """Summarise what an agent has done recently.

    Returns: {summary, count, entry_types}
    """
    entries = await vellum.read_recent_entries(
        agent.correspondence_sheet, hours=hours
    )
    agent_entries = [
        e for e in entries if e.get("author", "").startswith(agent.id)
    ]
    entry_types = {}
    for e in agent_entries:
        t = e.get("entry_type", "unknown")
        entry_types[t] = entry_types.get(t, 0) + 1

    return {
        "summary": f"{len(agent_entries)} entries in last {hours}h",
        "count": len(agent_entries),
        "entry_types": entry_types,
    }


async def run_agent_watcher(
    agents: list[AgentRecord],
    vellum: VellumClient,
    telegram: TelegramClient,
) -> list[Finding]:
    """Execute the AgentWatcher workflow.

    1. Check liveness for each agent
    2. Summarise recent output
    3. Emit telemetry to each agent's correspondence sheet
    4. Flag silence findings
    5. Write everything to Vellum
    """
    findings: list[Finding] = []
    telemetry: list[tuple[str, dict]] = []

    for agent in agents:
        # 1. Check liveness
        liveness = await check_agent_liveness(agent, vellum)

        # 2. Summarise recent output
        recent = await summarise_recent_output(agent, vellum)

        # 3. Build telemetry entry
        telemetry.append((agent.correspondence_sheet, {
            "entry_type": "telemetry",
            "author": "loom.agent_watcher",
            "content": f"agent {agent.id} liveness check",
            "epistemic_tier": "STRUCTURED",
            "metadata": {
                "agent_id": agent.id,
                "silence_minutes": liveness["minutes_since_last_signal"],
                "recent_output_summary": recent["summary"],
                "recent_output_count": recent["count"],
                "last_signal_at": liveness["last_signal_at"],
                "liveness_kind": liveness["kind"],
            },
        }))

        # 4. Flag silence
        if (
            agent.silence_alert_minutes is not None
            and liveness["minutes_since_last_signal"] > agent.silence_alert_minutes
        ):
            severity = (
                "critical"
                if liveness["minutes_since_last_signal"] > agent.silence_alert_minutes * 2
                else "warning"
            )
            findings.append(Finding(
                kind="agent_silent",
                severity=severity,
                source_workflow="loom.agent_watcher",
                evidence={
                    "agent_id": agent.id,
                    "silence_minutes": liveness["minutes_since_last_signal"],
                    "threshold": agent.silence_alert_minutes,
                },
                related_entity_ids=[agent.id],
            ))

    # 5. Write telemetry entries
    for sheet, entry in telemetry:
        await vellum.write_entry(sheet, entry)

    # Write findings to fleet sheet
    for f in findings:
        await vellum.write_entry(FLEET_SHEET, f.to_vellum_entry())
        if f.severity == "critical":
            await telegram.alert(
                f"AGENT CRITICAL: {f.evidence['agent_id']} silent "
                f"{f.evidence['silence_minutes']}m",
                f.evidence,
            )

    # Always write a run-summary
    await vellum.write_entry(FLEET_SHEET, {
        "entry_type": "health_check",
        "author": "loom.agent_watcher",
        "content": f"watcher complete: {len(agents)} agents, {len(findings)} findings",
        "epistemic_tier": "STRUCTURED",
        "metadata": {
            "agents_checked": len(agents),
            "finding_count": len(findings),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    })

    log.info("AgentWatcher complete: %d agents, %d findings", len(agents), len(findings))
    return findings
