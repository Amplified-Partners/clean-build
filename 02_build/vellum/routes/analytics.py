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
from vellum.models.entry import SheetEntry
from vellum.models.sheet import SheetMeta
from vellum.storage import get_store

log = logging.getLogger("vellum.analytics")
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# Singleton engine — initialised lazily
_engine: AnalyticsEngine | None = None

# Track whether we've already emitted a degradation warning this process
_degradation_witnessed: bool = False


def _get_engine() -> AnalyticsEngine:
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = AnalyticsEngine()
    return _engine


def reset_engine() -> None:
    """For testing."""
    global _engine, _degradation_witnessed  # noqa: PLW0603
    if _engine is not None:
        _engine.close()
    _engine = None
    _degradation_witnessed = False


async def _witness_degradation() -> None:
    """Write a CRITICAL telemetry entry when DuckDB is unavailable.

    Per Antigravity's flag: silent degradation is a silent-skip risk.
    If the analytics engine is down, the anti-shelfware wires are dead
    and nobody knows. This makes the degradation loud and witnessed.
    """
    global _degradation_witnessed  # noqa: PLW0603
    if _degradation_witnessed:
        return  # One critical entry per process lifetime, not per request
    _degradation_witnessed = True

    try:
        store = get_store()
        # Find or create the system-health sheet
        sheets = await store.list_sheets("ewan")
        health_sheet = None
        for s in sheets:
            if s.meta.mode == "telemetry" and "system-health" in s.meta.title:
                health_sheet = s
                break
        if health_sheet is None:
            meta = SheetMeta(
                title="system-health",
                mode="telemetry",
                created_by="vellum-analytics",
            )
            await store.create_sheet(meta)
            health_sheet = await store.get_sheet(meta.id)

        entry = SheetEntry(
            sheet_id=health_sheet.meta.id,
            author="vellum-analytics",
            content="CRITICAL: DuckDB not available — analytics degraded, anti-shelfware wires dead",
            prev_hash=health_sheet.latest_hash,
            entry_type="health_check",
            epistemic_tier="STRUCTURED",
            metadata={
                "severity": "critical",
                "component": "duckdb-analytics",
                "impact": "anti-shelfware wires inactive, named queries unavailable",
            },
        )
        await store.append_entry(health_sheet.meta.id, entry)
        log.critical("DuckDB unavailable — witnessed degradation in Vellum")
    except Exception:
        log.exception("Failed to witness DuckDB degradation")


@router.get("/status")
async def analytics_status() -> dict:
    """Check if DuckDB analytics is available.

    If degraded, writes a CRITICAL telemetry entry to Vellum so the
    BrainHealthCheck and AgentWatcher pick it up. Silent degradation
    is itself a failure mode.
    """
    if not DUCKDB_AVAILABLE:
        await _witness_degradation()
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
        await _witness_degradation()
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
        await _witness_degradation()
        raise HTTPException(status_code=503, detail="DuckDB not installed")

    count = await engine.load_from_store()
    return {"status": "ok", "entries_loaded": count}


@router.get("/log")
async def query_log() -> dict:
    """Return the query execution log for anti-shelfware tracking."""
    engine = _get_engine()
    return {"log": engine.get_query_log()}


# ---------------------------------------------------------------------------
# Brain analytics routes
# ---------------------------------------------------------------------------


@router.post("/brain/load")
async def load_brain_data() -> dict:
    """Load Brain tables from PostgreSQL into DuckDB.

    Requires BRAIN_READER_DSN environment variable. Read-only connection.
    Production uses Parquet snapshots; this endpoint is for on-demand loading.
    """
    engine = _get_engine()
    if not DUCKDB_AVAILABLE:
        await _witness_degradation()
        raise HTTPException(status_code=503, detail="DuckDB not installed")

    try:
        counts = await engine.load_brain_from_postgres()
        return {
            "status": "ok",
            "tables": counts,
            "total_rows": sum(counts.values()),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/brain/health")
async def brain_health(executed_by: str = "api") -> dict:
    """Brain health traffic light — single-glance score.

    Returns active packets, quarantined, stale, orphan counts, and a
    GREEN/AMBER/RED status. Glanceable governance.
    """
    engine = _get_engine()
    if not DUCKDB_AVAILABLE:
        await _witness_degradation()
        raise HTTPException(status_code=503, detail="DuckDB not installed")

    try:
        result = engine.run("brain_health_score", executed_by=executed_by)
        if result.row_count == 0:
            return {"status": "no_data", "message": "Brain tables not loaded — call /brain/load first"}
        row = dict(zip(result.columns, result.rows[0]))
        return {
            "health_status": row.get("health_status", "UNKNOWN"),
            "metrics": row,
            "output_hash": result.output_hash,
            "executed_by": result.executed_by,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="brain_health_score query not available")


@router.get("/brain/queries")
async def list_brain_queries() -> dict:
    """List all Brain-specific named queries."""
    from vellum.analytics.brain_queries import BRAIN_QUERY_REGISTRY_LITE
    return {
        "queries": sorted(BRAIN_QUERY_REGISTRY_LITE.keys()),
        "count": len(BRAIN_QUERY_REGISTRY_LITE),
    }


@router.get("/brain/log")
async def brain_load_log() -> dict:
    """Return the Brain data load audit log."""
    engine = _get_engine()
    return {"log": engine.get_brain_load_log()}
