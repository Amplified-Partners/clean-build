"""Stripe researcher — fetches yesterday's transactions for a tenant.

Signed-by: Devon-ae57 (daughter session of Devon-3397)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx

from . import ResearcherOutput


class StripeResearcher:
    """Fetches Stripe transaction data for the previous day."""

    def __init__(self) -> None:
        self._api_key: str = os.environ.get("STRIPE_API_KEY_JESMOND", "")
        self._base_url: str = "https://api.stripe.com/v1"

    async def fetch(self, tenant_id: str, date: datetime) -> ResearcherOutput:
        """Fetch yesterday's Stripe charges/refunds for the tenant."""
        try:
            return await self._fetch_internal(tenant_id, date)
        except Exception as exc:
            return ResearcherOutput(
                source="stripe",
                data={"error": str(exc)},
                summary="[unavailable]",
            )

    async def _fetch_internal(self, tenant_id: str, date: datetime) -> ResearcherOutput:
        yesterday_start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc) - timedelta(days=1)
        yesterday_end = yesterday_start + timedelta(days=1)

        headers = {"Authorization": f"Bearer {self._api_key}"}

        async with httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=30.0) as client:
            # Fetch charges
            charges_resp = await client.get(
                "/charges",
                params={
                    "created[gte]": int(yesterday_start.timestamp()),
                    "created[lt]": int(yesterday_end.timestamp()),
                    "limit": 100,
                },
            )
            charges_resp.raise_for_status()
            charges_data = charges_resp.json()

            # Fetch refunds
            refunds_resp = await client.get(
                "/refunds",
                params={
                    "created[gte]": int(yesterday_start.timestamp()),
                    "created[lt]": int(yesterday_end.timestamp()),
                    "limit": 100,
                },
            )
            refunds_resp.raise_for_status()
            refunds_data = refunds_resp.json()

            # Fetch disputes
            disputes_resp = await client.get(
                "/disputes",
                params={
                    "created[gte]": int(yesterday_start.timestamp()),
                    "created[lt]": int(yesterday_end.timestamp()),
                    "limit": 100,
                },
            )
            disputes_resp.raise_for_status()
            disputes_data = disputes_resp.json()

        charges = charges_data.get("data", [])
        refunds = refunds_data.get("data", [])
        disputes = disputes_data.get("data", [])

        # Calculate totals (amounts are in pence)
        total_revenue_pence = sum(c.get("amount", 0) for c in charges if c.get("status") == "succeeded")
        transaction_count = len([c for c in charges if c.get("status") == "succeeded"])
        refund_count = len(refunds)
        dispute_count = len(disputes)

        # Extract top services from charge descriptions
        descriptions: list[str] = []
        for charge in charges:
            desc = charge.get("description") or charge.get("statement_descriptor") or "Unknown service"
            descriptions.append(desc)

        # Count occurrences for top services
        service_counts: dict[str, int] = {}
        for desc in descriptions:
            service_counts[desc] = service_counts.get(desc, 0) + 1
        top_services = sorted(service_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        total_revenue_gbp = total_revenue_pence / 100.0

        data = {
            "total_revenue_gbp": total_revenue_gbp,
            "transaction_count": transaction_count,
            "top_services": [{"service": s, "count": c} for s, c in top_services],
            "refund_count": refund_count,
            "dispute_count": dispute_count,
            "date": yesterday_start.strftime("%Y-%m-%d"),
        }

        # Build summary
        summary_parts = [f"£{total_revenue_gbp:.2f} from {transaction_count} transactions"]
        if top_services:
            summary_parts.append(f"Top: {top_services[0][0]}")
        if refund_count:
            summary_parts.append(f"{refund_count} refund(s)")
        if dispute_count:
            summary_parts.append(f"{dispute_count} dispute(s)")

        return ResearcherOutput(
            source="stripe",
            data=data,
            summary=". ".join(summary_parts),
        )
