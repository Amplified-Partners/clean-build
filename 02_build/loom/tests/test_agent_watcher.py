"""AgentWatcher tests.

Covers:
  - Silent agent (no signal > threshold) produces agent_silent finding
  - Live agent produces telemetry only, no finding
  - Session-bound agents (Perplexity) don't trigger silence warnings
  - Run-summary always written
  - Critical silence triggers Telegram alert

Dana | 2026-05-20 | From Computer's Loom spec §8
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from loom.config import AgentRecord
from loom.integrations.telegram import TelegramClient
from loom.integrations.vellum import VellumClient
from loom.workflows.agent_watcher import (
    check_agent_liveness,
    run_agent_watcher,
    summarise_recent_output,
)
from vellum.storage import get_store, init_store
from vellum.storage.memory import MemorySheetStore


@pytest_asyncio.fixture(autouse=True)
async def _setup():
    store = await init_store()
    yield
    if isinstance(store, MemorySheetStore):
        store.clear()


def _make_agent(**overrides) -> AgentRecord:
    defaults = {
        "id": "test-agent",
        "type": "engineer",
        "vendor": "test",
        "seat": "testing",
        "expected_heartbeat_minutes": 60,
        "silence_alert_minutes": 180,
        "output_surface": "vellum",
        "correspondence_sheet": "agent-test",
    }
    defaults.update(overrides)
    return AgentRecord(**defaults)


class TestCheckAgentLiveness:
    @pytest.mark.asyncio
    async def test_session_bound_always_alive(self) -> None:
        """Session-bound agents should never trigger silence."""
        agent = _make_agent(
            id="perplexity-computer",
            expected_heartbeat_minutes=None,
            silence_alert_minutes=None,
        )
        vellum = VellumClient()
        liveness = await check_agent_liveness(agent, vellum)

        assert liveness["kind"] == "session-bound"
        assert liveness["minutes_since_last_signal"] == 0

    @pytest.mark.asyncio
    async def test_no_signal_returns_high_silence(self) -> None:
        """Agent with no recent entries should show high silence."""
        agent = _make_agent()
        vellum = VellumClient()
        liveness = await check_agent_liveness(agent, vellum)

        assert liveness["minutes_since_last_signal"] == 9999
        assert liveness["kind"] == "no_signal"


class TestRunAgentWatcher:
    @pytest.mark.asyncio
    async def test_silent_agent_produces_finding(self) -> None:
        """Agent exceeding silence threshold → agent_silent finding."""
        agents = [_make_agent(silence_alert_minutes=180)]
        vellum = VellumClient()
        telegram = TelegramClient()

        findings = await run_agent_watcher(agents, vellum, telegram)

        silent = [f for f in findings if f.kind == "agent_silent"]
        assert len(silent) == 1
        assert silent[0].evidence["agent_id"] == "test-agent"
        assert silent[0].evidence["silence_minutes"] > 180

    @pytest.mark.asyncio
    async def test_session_bound_no_silence_finding(self) -> None:
        """Session-bound agents should NOT produce silence findings."""
        agents = [_make_agent(
            id="perplexity",
            expected_heartbeat_minutes=None,
            silence_alert_minutes=None,
        )]
        vellum = VellumClient()
        telegram = TelegramClient()

        findings = await run_agent_watcher(agents, vellum, telegram)

        silent = [f for f in findings if f.kind == "agent_silent"]
        assert len(silent) == 0

    @pytest.mark.asyncio
    async def test_run_summary_always_written(self) -> None:
        """Watcher must always write a run-summary."""
        agents = [_make_agent()]
        vellum = VellumClient()
        telegram = TelegramClient()

        await run_agent_watcher(agents, vellum, telegram)

        store = get_store()
        sheets = await store.list_sheets("ewan")
        fleet = [s for s in sheets if s.meta.title == "agent-fleet"]
        assert len(fleet) == 1
        last = fleet[0].entries[-1]
        assert last.entry_type == "health_check"
        assert "watcher complete" in last.content

    @pytest.mark.asyncio
    async def test_critical_silence_triggers_telegram(self) -> None:
        """Double the silence threshold → critical → Telegram alert."""
        agents = [_make_agent(silence_alert_minutes=10)]
        vellum = VellumClient()
        telegram = TelegramClient()

        findings = await run_agent_watcher(agents, vellum, telegram)

        critical = [f for f in findings if f.severity == "critical"]
        assert len(critical) == 1
        assert len(telegram.get_alerts()) == 1
        assert "CRITICAL" in telegram.get_alerts()[0]["message"]

    @pytest.mark.asyncio
    async def test_telemetry_written_to_agent_sheet(self) -> None:
        """Each agent gets a telemetry entry on their correspondence sheet."""
        agents = [_make_agent(correspondence_sheet="agent-test")]
        vellum = VellumClient()
        telegram = TelegramClient()

        await run_agent_watcher(agents, vellum, telegram)

        store = get_store()
        sheets = await store.list_sheets("ewan")
        agent_sheet = [s for s in sheets if s.meta.title == "agent-test"]
        assert len(agent_sheet) == 1
        telemetry = [e for e in agent_sheet[0].entries if e.entry_type == "telemetry"]
        assert len(telemetry) >= 1
        assert telemetry[0].metadata["agent_id"] == "test-agent"

    @pytest.mark.asyncio
    async def test_multiple_agents_all_checked(self) -> None:
        """All agents in registry are checked."""
        agents = [
            _make_agent(id="devin", correspondence_sheet="agent-devin"),
            _make_agent(id="antigravity", correspondence_sheet="agent-antigravity"),
            _make_agent(
                id="perplexity",
                expected_heartbeat_minutes=None,
                silence_alert_minutes=None,
                correspondence_sheet="agent-perplexity",
            ),
        ]
        vellum = VellumClient()
        telegram = TelegramClient()

        findings = await run_agent_watcher(agents, vellum, telegram)

        # Devin and antigravity should have silence findings (no signal)
        silent = [f for f in findings if f.kind == "agent_silent"]
        assert len(silent) == 2
        silent_ids = {f.evidence["agent_id"] for f in silent}
        assert silent_ids == {"devin", "antigravity"}
