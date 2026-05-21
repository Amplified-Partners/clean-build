"""Loom configuration — env vars, defaults, agent registry, schedules.

Dana | 2026-05-20 | From Computer's Loom spec §3, §7
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class LoomConfig:
    """Environment-driven configuration for the Loom."""

    # Vellum
    vellum_base_url: str = ""
    vellum_api_token: str = ""

    # DuckDB / dq
    dq_base_url: str = ""

    # Pipe
    pipe_base_url: str = ""

    # Linear
    linear_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Temporal
    temporal_host: str = "localhost:7233"

    # Agent registry path
    agent_registry_path: str = ""

    @classmethod
    def from_env(cls) -> LoomConfig:
        return cls(
            vellum_base_url=os.environ.get("VELLUM_BASE_URL", "http://localhost:8400"),
            vellum_api_token=os.environ.get("VELLUM_API_TOKEN", ""),
            dq_base_url=os.environ.get("DQ_BASE_URL", "http://localhost:8500"),
            pipe_base_url=os.environ.get("PIPE_BASE_URL", "http://localhost:8600"),
            linear_api_key=os.environ.get("LINEAR_API_KEY", ""),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
            temporal_host=os.environ.get("TEMPORAL_HOST", "localhost:7233"),
            agent_registry_path=os.environ.get(
                "LOOM_AGENT_REGISTRY", "agents/registry.yaml"
            ),
        )


@dataclass
class AgentRecord:
    """An agent registered in the Loom's agent registry."""

    id: str
    type: str = "engineer"
    vendor: str = ""
    seat: str = ""
    poll_url: str | None = None
    expected_heartbeat_minutes: int | None = None
    silence_alert_minutes: int | None = None
    output_surface: str = "github_prs"
    correspondence_sheet: str = ""
    tier_ceiling: str = "STRUCTURED"


def load_agent_registry(path: str | Path) -> list[AgentRecord]:
    """Load the agent registry from a YAML file.

    The registry is canonical. Adding an agent means adding a
    YAML entry; the AgentWatcher picks it up on next run.
    No code changes for new agents.
    """
    path = Path(path)
    if not path.exists():
        return []

    with open(path) as f:
        data = yaml.safe_load(f)

    agents = []
    for entry in data.get("agents", []):
        agents.append(AgentRecord(
            id=entry["id"],
            type=entry.get("type", "engineer"),
            vendor=entry.get("vendor", ""),
            seat=entry.get("seat", ""),
            poll_url=entry.get("poll_url"),
            expected_heartbeat_minutes=entry.get("expected_heartbeat_minutes"),
            silence_alert_minutes=entry.get("silence_alert_minutes"),
            output_surface=entry.get("output_surface", "github_prs"),
            correspondence_sheet=entry.get("correspondence_sheet", f"agent-{entry['id']}"),
            tier_ceiling=entry.get("tier_ceiling", "STRUCTURED"),
        ))
    return agents


# Cron schedules — registered via Temporal Schedules API at startup
SCHEDULES = {
    "BrainHealthCheck": "30 3 * * *",       # nightly 03:30 UTC
    "AgentWatcher": "*/15 * * * *",          # every 15 min
    "KaizenProposalGenerator": "0 6 * * *",  # nightly 06:00 UTC
    "BudgetGuard": "0 * * * *",              # hourly
    # LoopCloser is event-driven, no cron
}
