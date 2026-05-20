"""Analytics routes — DuckDB-powered read-side queries.

Exposes named queries over Vellum data via REST. Every query
execution is witnessed (logged with identity and output hash).

The analytics engine loads from the Vellum store on demand
(dev/test) or from Parquet snapshots (production).

Dana | 2026-05-20 | Analytics routes — the Fourth Seat
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from vellum.analytics.engine import DUCKDB_AVAILABLE, AnalyticsEngine

log = logging.getLogger("vellum.analytics")
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# Singleton engine — initialised lazily
_engine: AnalyticsEngine | None = None


def _get_engine() -> AnalyticsEngine:
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = AnalyticsEngine()
    return _engine


def reset_engine() -> None:
    """For testing."""
    global _engine  # noqa: PLW0603
    if _engine is not None:
        _engine.close()
    _engine = None


@router.get("/status")
async def analytics_status() -> dict:
    """Check if DuckDB analytics is available."""
    return {
        "available": DUCKDB_AVAILABLE,
        "queries": _get_engine().list_queries() if DUCKDB_AVAILABLE else [],
    }


@router.get("/queries")
async def list_queries() -> dict:
    """List all available named queries."""
    engine = _get_engine()
    return {"queries": engine.list_queries()}


@router.post("/run/{query_name}")
async def run_query(query_name: str, executed_by: str = "api") -> dict:
    """Run a named analytics query.

    Loads fresh data from the Vellum store, executes the query,
    and returns results with the output hash for witnessing.
    """
    engine = _get_engine()

    if not DUCKDB_AVAILABLE:
        raise HTTPException(status_code=503, detail="DuckDB not installed")

    try:
        # Load latest data from store
        await engine.load_from_store()
        result = engine.run(query_name, executed_by=executed_by)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result.to_dict()


@router.post("/refresh")
async def refresh_data() -> dict:
    """Reload data from the Vellum store into DuckDB."""
    engine = _get_engine()
    if not DUCKDB_AVAILABLE:
        raise HTTPException(status_code=503, detail="DuckDB not installed")

    count = await engine.load_from_store()
    return {"status": "ok", "entries_loaded": count}


@router.get("/log")
async def query_log() -> dict:
    """Return the query execution log for anti-shelfware tracking."""
    engine = _get_engine()
    return {"log": engine.get_query_log()}
