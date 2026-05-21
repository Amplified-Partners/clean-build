"""test_witness_on_every_write — invariant §6.2.

Every workflow run produces at least one Vellum entry.
Even if no findings, write a run-summary.
Silence from a watchdog is itself a signal.

Dana | 2026-05-20 | From Computer's Loom spec §6
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from loom.config import AgentRecord
from loom.integrations.dq import DqClient
from loom.integrations.telegram import TelegramClient
from loom.integrations.vellum import VellumClient
from loom.workflows.agent_watcher import run_agent_watcher
from loom.workflows.brain_health import run_brain_health_check
from loom.workflows.budget_guard import run_budget_guard
from vellum.storage import get_store, init_store
from vellum.storage.memory import MemorySheetStore


@pytest_asyncio.fixture(autouse=True)
async def _setup():
    store = await init_store()
    yield
    if isinstance(store, MemorySheetStore):
        store.clear()


class TestWitnessOnEveryWrite:
    """Every workflow MUST write at least one Vellum entry per run."""

    @pytest.mark.asyncio
    async def test_brain_health_always_witnesses(self) -> None:
        vellum = VellumClient()
        dq = DqClient()
        telegram = TelegramClient()

        await run_brain_health_check(vellum, dq, telegram)

        store = get_store()
        sheets = await store.list_sheets("ewan")
        brain = [s for s in sheets if s.meta.title == "brain-health"]
        assert len(brain) == 1
        assert len(brain[0].entries) >= 1

    @pytest.mark.asyncio
    async def test_agent_watcher_always_witnesses(self) -> None:
        vellum = VellumClient()
        telegram = TelegramClient()

        await run_agent_watcher([], vellum, telegram)

        store = get_store()
        sheets = await store.list_sheets("ewan")
        fleet = [s for s in sheets if s.meta.title == "agent-fleet"]
        assert len(fleet) == 1
        assert len(fleet[0].entries) >= 1

    @pytest.mark.asyncio
    async def test_budget_guard_always_witnesses(self) -> None:
        vellum = VellumClient()
        telegram = TelegramClient()

        await run_budget_guard(vellum, telegram, spend_data={}, caps={})

        store = get_store()
        sheets = await store.list_sheets("ewan")
        budget = [s for s in sheets if s.meta.title == "budget-log"]
        assert len(budget) == 1
        assert len(budget[0].entries) >= 1

    @pytest.mark.asyncio
    async def test_all_entries_have_authors(self) -> None:
        """Every witnessed entry must have an author (attribution)."""
        vellum = VellumClient()
        dq = DqClient()
        telegram = TelegramClient()

        await run_brain_health_check(vellum, dq, telegram)
        await run_budget_guard(vellum, telegram, spend_data={}, caps={})

        store = get_store()
        sheets = await store.list_sheets("ewan")
        for s in sheets:
            for e in s.entries:
                assert e.author, f"Entry {e.id} has no author"
                assert e.author.startswith("loom."), (
                    f"Entry {e.id} author '{e.author}' doesn't start with 'loom.'"
                )
