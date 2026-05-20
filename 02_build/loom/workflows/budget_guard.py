"""BudgetGuard — hourly vendor spend monitoring.

Sums vendor spend, compares to caps, alerts on projected
overruns. Critical = halt non-essential workflows for that
vendor. Warning = open Linear issue.

Schedule: hourly.

Dana | 2026-05-20 | From Computer's Loom spec §5.5
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from loom.findings import Finding
from loom.integrations.telegram import TelegramClient
from loom.integrations.vellum import VellumClient

log = logging.getLogger("loom.workflows.budget_guard")

SHEET_NAME = "budget-log"

# Default budget caps per vendor (USD/month)
DEFAULT_CAPS: dict[str, dict] = {
    "anthropic": {"monthly_cap_usd": 500},
    "openai": {"monthly_cap_usd": 200},
    "deepseek": {"monthly_cap_usd": 100},
    "google": {"monthly_cap_usd": 100},
    "perplexity": {"monthly_cap_usd": 50},
}


async def run_budget_guard(
    vellum: VellumClient,
    telegram: TelegramClient,
    spend_data: dict | None = None,
    caps: dict | None = None,
) -> list[Finding]:
    """Execute the BudgetGuard workflow.

    1. Load vendor spend data
    2. Compare to caps
    3. Flag warnings (>85%) and critical (>100%)
    4. Write findings + alert on critical
    5. Always write run-summary
    """
    if caps is None:
        caps = DEFAULT_CAPS

    findings: list[Finding] = []

    if spend_data is None:
        spend_data = {}

    for vendor, vendor_spend in spend_data.items():
        cap_info = caps.get(vendor)
        if cap_info is None:
            continue

        cap = cap_info.get("monthly_cap_usd", 0)
        if cap <= 0:
            continue

        current = vendor_spend.get("this_month_so_far", 0)
        days_into_month = vendor_spend.get("days_into_month", 1)
        projected = current * (30 / max(days_into_month, 1))
        ratio = projected / cap

        if ratio > 1.0:
            findings.append(Finding(
                kind="budget_critical",
                severity="critical",
                source_workflow="loom.budget_guard",
                evidence={
                    "vendor": vendor,
                    "projected": round(projected, 2),
                    "cap": cap,
                    "ratio": round(ratio, 4),
                    "current_spend": current,
                    "days_into_month": days_into_month,
                },
            ))
        elif ratio > 0.85:
            findings.append(Finding(
                kind="budget_warning",
                severity="warning",
                source_workflow="loom.budget_guard",
                evidence={
                    "vendor": vendor,
                    "projected": round(projected, 2),
                    "cap": cap,
                    "ratio": round(ratio, 4),
                    "current_spend": current,
                    "days_into_month": days_into_month,
                },
            ))

    # Write findings
    for f in findings:
        await vellum.write_entry(SHEET_NAME, f.to_vellum_entry())
        if f.severity == "critical":
            await telegram.alert(
                f"BUDGET CRITICAL: {f.evidence['vendor']} "
                f"projected ${f.evidence['projected']:.0f} / "
                f"cap ${f.evidence['cap']:.0f}",
                f.evidence,
            )

    # Always write run-summary
    await vellum.write_entry(SHEET_NAME, {
        "entry_type": "health_check",
        "author": "loom.budget_guard",
        "content": f"budget check complete: {len(findings)} findings",
        "epistemic_tier": "STRUCTURED",
        "metadata": {
            "finding_count": len(findings),
            "vendors_checked": len(spend_data),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    })

    log.info("BudgetGuard complete: %d findings", len(findings))
    return findings
