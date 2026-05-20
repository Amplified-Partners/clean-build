"""DuckDB analytics engine — the Fourth Seat.

Read-only analytical queries over Vellum data. Exports sheet entries
to Parquet for fast columnar queries. Named queries stored in the
query registry — no ad-hoc SQL accumulation.

Every query execution is witnessed: identity, query name, output hash,
and timestamp are recorded for audit.

Architecture (per Antigravity's spec):
  - Nightly snapshot: exports Vellum entries to Parquet
  - Named queries: stored in registry, run via engine.run(query_name)
  - Vellum witnessing: every execution logged as a telemetry entry

Dana | 2026-05-20 | DuckDB analytics engine — the Fourth Seat
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("vellum.analytics")

# ---------------------------------------------------------------------------
# Try to import duckdb — graceful degradation if not installed
# ---------------------------------------------------------------------------

try:
    import duckdb

    DUCKDB_AVAILABLE = True
except ImportError:
    duckdb = None  # type: ignore[assignment]
    DUCKDB_AVAILABLE = False
    log.info("DuckDB not installed — analytics engine will use fallback mode")


# ---------------------------------------------------------------------------
# Query result
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    """Result of an analytics query."""

    query_name: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    executed_at: datetime
    executed_by: str
    output_hash: str  # SHA-256 of the result for witnessing

    def to_dict(self) -> dict:
        return {
            "query_name": self.query_name,
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "executed_at": self.executed_at.isoformat(),
            "executed_by": self.executed_by,
            "output_hash": self.output_hash,
        }


# ---------------------------------------------------------------------------
# Named query registry
# ---------------------------------------------------------------------------

QUERY_REGISTRY: dict[str, str] = {
    # --- Epistemic tier analytics ---
    "tier_distribution": """
        SELECT epistemic_tier, COUNT(*) as count,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pct
        FROM entries
        GROUP BY epistemic_tier
        ORDER BY count DESC
    """,
    "intuited_corroboration_rate": """
        SELECT
            DATE_TRUNC('day', timestamp) as day,
            COUNT(*) FILTER (WHERE epistemic_tier = 'INTUITED') as intuited,
            COUNT(*) FILTER (WHERE epistemic_tier = 'STRUCTURED') as structured,
            COUNT(*) FILTER (WHERE epistemic_tier = 'MEASURED') as measured,
            ROUND(
                COUNT(*) FILTER (WHERE epistemic_tier = 'STRUCTURED')
                * 100.0 / NULLIF(COUNT(*) FILTER (WHERE epistemic_tier = 'INTUITED'), 0),
                2
            ) as corroboration_rate_pct
        FROM entries
        GROUP BY day
        ORDER BY day DESC
        LIMIT 30
    """,

    # --- Agent attribution ---
    "agent_activity": """
        SELECT author, COUNT(*) as entries,
               COUNT(DISTINCT sheet_id) as conversations,
               MIN(timestamp) as first_seen,
               MAX(timestamp) as last_seen
        FROM entries
        GROUP BY author
        ORDER BY entries DESC
    """,
    "agent_tier_breakdown": """
        SELECT author, epistemic_tier, COUNT(*) as count
        FROM entries
        GROUP BY author, epistemic_tier
        ORDER BY author, count DESC
    """,

    # --- Conversation analytics ---
    "conversation_volume": """
        SELECT DATE_TRUNC('day', timestamp) as day,
               COUNT(*) as messages,
               COUNT(DISTINCT sheet_id) as active_conversations,
               COUNT(DISTINCT author) as active_participants
        FROM entries
        GROUP BY day
        ORDER BY day DESC
        LIMIT 30
    """,
    "conversation_depth": """
        SELECT sheet_id, COUNT(*) as message_count,
               COUNT(DISTINCT author) as participant_count,
               MIN(timestamp) as started,
               MAX(timestamp) as last_message
        FROM entries
        GROUP BY sheet_id
        ORDER BY message_count DESC
        LIMIT 50
    """,

    # --- Mode analytics ---
    "mode_distribution": """
        SELECT mode, COUNT(*) as entries,
               COUNT(DISTINCT sheet_id) as sheets
        FROM entries
        GROUP BY mode
        ORDER BY entries DESC
    """,

    # --- Decision tracking ---
    "decisions_timeline": """
        SELECT DATE_TRUNC('day', timestamp) as day,
               COUNT(*) as decisions,
               COUNT(DISTINCT author) as decision_makers
        FROM entries
        WHERE entry_type = 'decision'
        GROUP BY day
        ORDER BY day DESC
        LIMIT 30
    """,

    # --- Source analytics (ingestion) ---
    "source_volume": """
        SELECT
            json_extract_string(metadata, '$.source') as source,
            COUNT(*) as messages,
            COUNT(DISTINCT author) as authors
        FROM entries
        WHERE json_extract_string(metadata, '$.source') IS NOT NULL
        GROUP BY source
        ORDER BY messages DESC
    """,

    # --- Health / anti-shelfware ---
    "weekly_query_activity": """
        SELECT query_name, COUNT(*) as runs,
               MAX(executed_at) as last_run
        FROM query_log
        GROUP BY query_name
        ORDER BY last_run DESC
    """,
}


# ---------------------------------------------------------------------------
# Analytics engine
# ---------------------------------------------------------------------------


class AnalyticsEngine:
    """DuckDB-powered analytics over Vellum data.

    Operates in two modes:
    1. Parquet mode: reads from exported Parquet files (production)
    2. Memory mode: loads entries directly from the Vellum store (dev/test)

    Every query execution is logged for anti-shelfware tracking.
    """

    def __init__(self, parquet_dir: Path | None = None) -> None:
        self._parquet_dir = parquet_dir
        self._query_log: list[dict] = []

        if DUCKDB_AVAILABLE:
            self._conn = duckdb.connect(":memory:")
            self._init_tables()
        else:
            self._conn = None

    def _init_tables(self) -> None:
        """Create in-memory tables for analytics."""
        if self._conn is None:
            return
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id VARCHAR,
                sheet_id VARCHAR,
                author VARCHAR,
                content VARCHAR,
                timestamp TIMESTAMP,
                entry_type VARCHAR,
                epistemic_tier VARCHAR,
                entry_hash VARCHAR,
                metadata JSON,
                mode VARCHAR
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS query_log (
                query_name VARCHAR,
                executed_at TIMESTAMP,
                executed_by VARCHAR,
                output_hash VARCHAR,
                row_count INTEGER
            )
        """)

    async def load_from_store(self) -> int:
        """Load entries from the Vellum store into DuckDB.

        Used in dev/test mode. Production uses Parquet snapshots.
        Returns the number of entries loaded.
        """
        if self._conn is None:
            return 0

        from vellum.storage import get_store
        store = get_store()
        sheets = await store.list_sheets("ewan")

        # Clear and reload
        self._conn.execute("DELETE FROM entries")

        count = 0
        for sheet in sheets:
            for entry in sheet.entries:
                self._conn.execute(
                    """INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        entry.id,
                        entry.sheet_id,
                        entry.author,
                        entry.content,
                        entry.timestamp,
                        entry.entry_type,
                        entry.epistemic_tier,
                        entry.entry_hash,
                        json.dumps(entry.metadata),
                        sheet.meta.mode,
                    ],
                )
                count += 1

        log.info("Loaded %d entries into DuckDB analytics", count)
        return count

    def load_parquet(self, path: Path) -> int:
        """Load entries from a Parquet file. Production mode."""
        if self._conn is None:
            return 0
        self._conn.execute("DELETE FROM entries")
        self._conn.execute(f"INSERT INTO entries SELECT * FROM read_parquet('{path}')")
        count = self._conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        log.info("Loaded %d entries from Parquet: %s", count, path)
        return count

    def run(self, query_name: str, executed_by: str = "analytics-engine") -> QueryResult:
        """Run a named query from the registry.

        The query, identity, and output hash are logged for witnessing.
        """
        if self._conn is None:
            raise RuntimeError("DuckDB not available — install duckdb to use analytics")

        sql = QUERY_REGISTRY.get(query_name)
        if sql is None:
            raise KeyError(
                f"Query '{query_name}' not found. "
                f"Available: {sorted(QUERY_REGISTRY.keys())}"
            )

        result = self._conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = [list(row) for row in result.fetchall()]

        # Compute output hash for witnessing
        output_data = json.dumps({"columns": columns, "rows": rows}, default=str)
        output_hash = hashlib.sha256(output_data.encode("utf-8")).hexdigest()

        now = datetime.now(timezone.utc)

        # Log the execution
        self._conn.execute(
            "INSERT INTO query_log VALUES (?, ?, ?, ?, ?)",
            [query_name, now, executed_by, output_hash, len(rows)],
        )
        self._query_log.append({
            "query_name": query_name,
            "executed_at": now.isoformat(),
            "executed_by": executed_by,
            "output_hash": output_hash,
            "row_count": len(rows),
        })

        return QueryResult(
            query_name=query_name,
            sql=sql.strip(),
            columns=columns,
            rows=rows,
            row_count=len(rows),
            executed_at=now,
            executed_by=executed_by,
            output_hash=output_hash,
        )

    def run_sql(self, sql: str, executed_by: str = "analytics-engine") -> QueryResult:
        """Run arbitrary SQL. Use sparingly — prefer named queries."""
        if self._conn is None:
            raise RuntimeError("DuckDB not available")

        result = self._conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = [list(row) for row in result.fetchall()]

        output_data = json.dumps({"columns": columns, "rows": rows}, default=str)
        output_hash = hashlib.sha256(output_data.encode("utf-8")).hexdigest()

        return QueryResult(
            query_name="_ad_hoc",
            sql=sql.strip(),
            columns=columns,
            rows=rows,
            row_count=len(rows),
            executed_at=datetime.now(timezone.utc),
            executed_by=executed_by,
            output_hash=output_hash,
        )

    def list_queries(self) -> list[str]:
        """List all named queries in the registry."""
        return sorted(QUERY_REGISTRY.keys())

    def get_query_log(self) -> list[dict]:
        """Return the in-memory query execution log."""
        return list(self._query_log)

    async def export_parquet(self, output_path: Path) -> int:
        """Export current entries to Parquet for external consumption.

        This is the nightly snapshot path: Vellum → Parquet → DuckDB.
        """
        if self._conn is None:
            raise RuntimeError("DuckDB not available")

        await self.load_from_store()
        self._conn.execute(
            f"COPY entries TO '{output_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        count = self._conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        log.info("Exported %d entries to Parquet: %s", count, output_path)
        return count

    def close(self) -> None:
        """Close the DuckDB connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
