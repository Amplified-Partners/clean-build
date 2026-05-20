"""DuckDB (dq) integration — run named queries from the manifest.

In test mode, uses the Vellum analytics engine directly.
In production, calls the dq REST API or CLI.

Dana | 2026-05-20 | From Computer's Loom spec §2.2
"""

from __future__ import annotations

import logging

log = logging.getLogger("loom.integrations.dq")


class DqClient:
    """Adapter for running DuckDB named queries."""

    def __init__(self, use_engine: bool = True) -> None:
        self._use_engine = use_engine

    async def run(self, query_name: str, executed_by: str = "loom") -> dict:
        """Run a named DuckDB query and return the result.

        Returns a dict with at minimum: columns, rows, output_hash.
        """
        if self._use_engine:
            from vellum.analytics.engine import DUCKDB_AVAILABLE, AnalyticsEngine

            if not DUCKDB_AVAILABLE:
                log.warning("DuckDB not available — returning empty result")
                return {"columns": [], "rows": [], "output_hash": "", "available": False}

            engine = AnalyticsEngine()
            await engine.load_from_store()
            result = engine.run(query_name, executed_by=executed_by)
            data = result.to_dict()
            engine.close()
            return data

        # Production: HTTP call to dq service
        raise NotImplementedError("HTTP dq client not yet implemented")

    async def run_budget_query(self, executed_by: str = "loom.budget_guard") -> dict:
        """Run the budget spend query. Returns vendor-level spend data.

        In test mode, returns mock data. Production queries cost-log.
        """
        return await self.run("source_volume", executed_by=executed_by)
