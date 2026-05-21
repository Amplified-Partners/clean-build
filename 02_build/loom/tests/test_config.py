"""Config tests — agent registry loading and schedule validation.

Dana | 2026-05-20
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from loom.config import (
    AgentRecord,
    LoomConfig,
    SCHEDULES,
    load_agent_registry,
)

REGISTRY_PATH = Path(__file__).parent.parent / "agents" / "registry.yaml"


class TestAgentRegistry:
    def test_load_registry_from_yaml(self) -> None:
        """The canonical registry.yaml must load correctly."""
        agents = load_agent_registry(REGISTRY_PATH)
        assert len(agents) == 5

        ids = {a.id for a in agents}
        assert ids == {"devin", "antigravity", "perplexity-computer", "cove", "northumbrian-sweep"}

    def test_all_agents_have_structured_ceiling(self) -> None:
        """All agents are capped at STRUCTURED per spec."""
        agents = load_agent_registry(REGISTRY_PATH)
        for agent in agents:
            assert agent.tier_ceiling == "STRUCTURED", (
                f"Agent {agent.id} has tier_ceiling={agent.tier_ceiling}"
            )

    def test_session_bound_agents(self) -> None:
        """Session-bound agents have null heartbeat and silence thresholds."""
        agents = load_agent_registry(REGISTRY_PATH)
        perplexity = [a for a in agents if a.id == "perplexity-computer"][0]
        assert perplexity.expected_heartbeat_minutes is None
        assert perplexity.silence_alert_minutes is None

        sweep = [a for a in agents if a.id == "northumbrian-sweep"][0]
        assert sweep.expected_heartbeat_minutes is None
        assert sweep.silence_alert_minutes is None

    def test_daemon_agents_have_thresholds(self) -> None:
        """Daemon agents must have heartbeat and silence thresholds."""
        agents = load_agent_registry(REGISTRY_PATH)
        cove = [a for a in agents if a.id == "cove"][0]
        assert cove.expected_heartbeat_minutes == 5
        assert cove.silence_alert_minutes == 15

    def test_load_missing_file_returns_empty(self) -> None:
        """Missing registry file → empty list, not crash."""
        agents = load_agent_registry("/nonexistent/path.yaml")
        assert agents == []

    def test_correspondence_sheets_unique(self) -> None:
        """Each agent must have a unique correspondence sheet."""
        agents = load_agent_registry(REGISTRY_PATH)
        sheets = [a.correspondence_sheet for a in agents]
        assert len(sheets) == len(set(sheets))


class TestSchedules:
    def test_all_pr1_workflows_scheduled(self) -> None:
        """PR1 workflows must have cron schedules."""
        assert "BrainHealthCheck" in SCHEDULES
        assert "AgentWatcher" in SCHEDULES
        assert "BudgetGuard" in SCHEDULES

    def test_loop_closer_not_scheduled(self) -> None:
        """LoopCloser is event-driven, not cron."""
        assert "LoopCloser" not in SCHEDULES


class TestLoomConfig:
    def test_from_env_defaults(self) -> None:
        """Config loads with sensible defaults."""
        config = LoomConfig.from_env()
        assert config.temporal_host == "localhost:7233"
        assert config.vellum_base_url == "http://localhost:8400"
