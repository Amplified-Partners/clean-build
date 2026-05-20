"""BudgetGuard tests.

Covers:
  - Projected overshoot triggers critical alert
  - Near-cap triggers warning
  - Under-cap produces no findings
  - Missing cap is silently skipped
  - Run-summary always written

Dana | 2026-05-20 | From Computer's Loom spec §8
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from loom.integrations.telegram import TelegramClient
from loom.integrations.vellum import VellumClient
from loom.workflows.budget_guard import run_budget_guard
from vellum.storage import get_store, init_store
from vellum.storage.memory import MemorySheetStore


@pytest_asyncio.fixture(autouse=True)
async def _setup():
    store = await init_store()
    yield
    if isinstance(store, MemorySheetStore):
        store.clear()


class TestBudgetGuard:
    @pytest.mark.asyncio
    async def test_projected_overshoot_is_critical(self) -> None:
        """Vendor projected to exceed cap → critical finding."""
        vellum = VellumClient()
        telegram = TelegramClient()

        spend = {
            "anthropic": {"this_month_so_far": 400, "days_into_month": 15},
        }
        caps = {"anthropic": {"monthly_cap_usd": 500}}

        findings = await run_budget_guard(vellum, telegram, spend, caps)

        critical = [f for f in findings if f.kind == "budget_critical"]
        assert len(critical) == 1
        assert critical[0].evidence["vendor"] == "anthropic"
        assert critical[0].evidence["projected"] > 500

    @pytest.mark.asyncio
    async def test_near_cap_is_warning(self) -> None:
        """Vendor at 85-100% of cap → warning finding."""
        vellum = VellumClient()
        telegram = TelegramClient()

        # 300 spent in 15 days → projected 600, cap 650 → ratio ~0.92 → warning
        spend = {
            "openai": {"this_month_so_far": 300, "days_into_month": 15},
        }
        caps = {"openai": {"monthly_cap_usd": 650}}

        findings = await run_budget_guard(vellum, telegram, spend, caps)

        warnings = [f for f in findings if f.kind == "budget_warning"]
        assert len(warnings) == 1
        assert warnings[0].severity == "warning"

    @pytest.mark.asyncio
    async def test_under_cap_no_findings(self) -> None:
        """Vendor well under cap → no findings (besides run-summary)."""
        vellum = VellumClient()
        telegram = TelegramClient()

        spend = {
            "deepseek": {"this_month_so_far": 10, "days_into_month": 15},
        }
        caps = {"deepseek": {"monthly_cap_usd": 100}}

        findings = await run_budget_guard(vellum, telegram, spend, caps)
        assert len(findings) == 0

    @pytest.mark.asyncio
    async def test_missing_cap_skipped(self) -> None:
        """Vendor with no cap defined → silently skipped."""
        vellum = VellumClient()
        telegram = TelegramClient()

        spend = {
            "unknown_vendor": {"this_month_so_far": 9999, "days_into_month": 1},
        }
        caps = {}  # No caps defined

        findings = await run_budget_guard(vellum, telegram, spend, caps)
        assert len(findings) == 0

    @pytest.mark.asyncio
    async def test_critical_triggers_telegram(self) -> None:
        """Critical budget finding must trigger Telegram alert."""
        vellum = VellumClient()
        telegram = TelegramClient()

        spend = {
            "anthropic": {"this_month_so_far": 600, "days_into_month": 10},
        }
        caps = {"anthropic": {"monthly_cap_usd": 500}}

        await run_budget_guard(vellum, telegram, spend, caps)

        alerts = telegram.get_alerts()
        assert len(alerts) == 1
        assert "BUDGET CRITICAL" in alerts[0]["message"]
        assert "anthropic" in alerts[0]["message"]

    @pytest.mark.asyncio
    async def test_run_summary_always_written(self) -> None:
        """Run-summary must always be written, even with no findings."""
        vellum = VellumClient()
        telegram = TelegramClient()

        await run_budget_guard(vellum, telegram, spend_data={}, caps={})

        store = get_store()
        sheets = await store.list_sheets("ewan")
        budget = [s for s in sheets if s.meta.title == "budget-log"]
        assert len(budget) == 1
        last = budget[0].entries[-1]
        assert last.entry_type == "health_check"
        assert "budget check complete" in last.content

    @pytest.mark.asyncio
    async def test_multiple_vendors(self) -> None:
        """Multiple vendors checked in one run."""
        vellum = VellumClient()
        telegram = TelegramClient()

        spend = {
            "anthropic": {"this_month_so_far": 600, "days_into_month": 15},
            "openai": {"this_month_so_far": 10, "days_into_month": 15},
            "deepseek": {"this_month_so_far": 80, "days_into_month": 15},
        }
        caps = {
            "anthropic": {"monthly_cap_usd": 500},
            "openai": {"monthly_cap_usd": 200},
            "deepseek": {"monthly_cap_usd": 100},
        }

        findings = await run_budget_guard(vellum, telegram, spend, caps)

        # Anthropic: 600*(30/15)=1200/500=2.4 → critical
        # OpenAI: 10*(30/15)=20/200=0.1 → under
        # DeepSeek: 80*(30/15)=160/100=1.6 → critical
        critical = [f for f in findings if f.kind == "budget_critical"]
        assert len(critical) == 2
        vendors = {f.evidence["vendor"] for f in critical}
        assert vendors == {"anthropic", "deepseek"}
