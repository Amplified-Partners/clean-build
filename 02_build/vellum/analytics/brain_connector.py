"""Brain connector — bridges PostgreSQL Brain tables to DuckDB analytics.

Reads from the Brain's PostgreSQL (brain_packets, brain_documents,
knowledge_vectors, curation runs, dedup clusters, evidence links)
and loads into DuckDB for fast analytical queries.

This is a READ-ONLY connector. DuckDB is the Fourth Seat — it queries
already-written-down material. It does not write to the Brain.

Production path: PostgreSQL → Parquet (nightly cron) → DuckDB
Dev/test path: PostgreSQL → DuckDB (direct load via asyncpg)

Dana | 2026-05-21 | Brain connector for DuckDB analytics
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("vellum.analytics.brain")

# ---------------------------------------------------------------------------
# DSN — read-only connection to the Brain
# ---------------------------------------------------------------------------

BRAIN_READER_DSN = os.environ.get("BRAIN_READER_DSN", "")


def _get_dsn() -> str:
    """Get the Brain reader DSN. Raises if not configured."""
    dsn = BRAIN_READER_DSN or os.environ.get("BRAIN_READER_DSN", "")
    if not dsn:
        raise RuntimeError(
            "BRAIN_READER_DSN not set — cannot connect to Brain. "
            "Set it to the PostgreSQL connection string for brain_reader."
        )
    return dsn


# ---------------------------------------------------------------------------
# Brain table schemas for DuckDB
# ---------------------------------------------------------------------------

BRAIN_TABLES = {
    "brain_packets": """
        CREATE TABLE IF NOT EXISTS brain_packets (
            packet_id VARCHAR,
            packet_type VARCHAR,
            title VARCHAR,
            summary VARCHAR,
            status VARCHAR,
            route VARCHAR,
            epistemic_tier VARCHAR,
            claim_status VARCHAR,
            decision_state VARCHAR,
            valid_from TIMESTAMP,
            valid_to TIMESTAMP,
            last_verified_at TIMESTAMP,
            source_document_id VARCHAR,
            canonical_packet_id VARCHAR,
            metadata JSON,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """,
    "brain_documents": """
        CREATE TABLE IF NOT EXISTS brain_documents (
            document_id VARCHAR,
            source_path VARCHAR,
            source_system VARCHAR,
            source_id VARCHAR,
            file_hash_sha256 VARCHAR,
            title VARCHAR,
            document_type VARCHAR,
            created_at TIMESTAMP,
            ingested_at TIMESTAMP,
            pipeline_version VARCHAR,
            chunk_count INTEGER,
            status VARCHAR
        )
    """,
    "brain_curation_runs": """
        CREATE TABLE IF NOT EXISTS brain_curation_runs (
            run_id VARCHAR,
            stage VARCHAR,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            code_version VARCHAR,
            config_hash VARCHAR,
            input_scope JSON,
            metrics JSON,
            status VARCHAR,
            error VARCHAR
        )
    """,
    "brain_dedupe_clusters": """
        CREATE TABLE IF NOT EXISTS brain_dedupe_clusters (
            cluster_id VARCHAR,
            cluster_type VARCHAR,
            method VARCHAR,
            canonical_member_id VARCHAR,
            metadata JSON,
            created_at TIMESTAMP
        )
    """,
    "brain_dedupe_members": """
        CREATE TABLE IF NOT EXISTS brain_dedupe_members (
            member_id VARCHAR,
            cluster_id VARCHAR,
            chunk_id VARCHAR,
            member_role VARCHAR,
            confidence REAL,
            created_at TIMESTAMP
        )
    """,
    "brain_packet_evidence": """
        CREATE TABLE IF NOT EXISTS brain_packet_evidence (
            evidence_id VARCHAR,
            packet_id VARCHAR,
            chunk_id VARCHAR,
            evidence_role VARCHAR,
            confidence REAL,
            created_at TIMESTAMP
        )
    """,
    "brain_relationships": """
        CREATE TABLE IF NOT EXISTS brain_relationships (
            relationship_id VARCHAR,
            source_packet_id VARCHAR,
            target_packet_id VARCHAR,
            predicate VARCHAR,
            evidence_count INTEGER,
            confidence REAL,
            metadata JSON,
            created_at TIMESTAMP
        )
    """,
    "brain_validation_samples": """
        CREATE TABLE IF NOT EXISTS brain_validation_samples (
            sample_id VARCHAR,
            packet_id VARCHAR,
            verdict VARCHAR,
            reviewed_by VARCHAR,
            reviewed_at TIMESTAMP,
            notes VARCHAR,
            metrics JSON
        )
    """,
}

# Column lists for INSERT (must match table order above)
_BRAIN_COLUMNS = {
    "brain_packets": [
        "packet_id", "packet_type", "title", "summary", "status", "route",
        "epistemic_tier", "claim_status", "decision_state", "valid_from",
        "valid_to", "last_verified_at", "source_document_id",
        "canonical_packet_id", "metadata", "created_at", "updated_at",
    ],
    "brain_documents": [
        "document_id", "source_path", "source_system", "source_id",
        "file_hash_sha256", "title", "document_type", "created_at",
        "ingested_at", "pipeline_version", "chunk_count", "status",
    ],
    "brain_curation_runs": [
        "run_id", "stage", "started_at", "completed_at", "code_version",
        "config_hash", "input_scope", "metrics", "status", "error",
    ],
    "brain_dedupe_clusters": [
        "cluster_id", "cluster_type", "method", "canonical_member_id",
        "metadata", "created_at",
    ],
    "brain_dedupe_members": [
        "member_id", "cluster_id", "chunk_id", "member_role",
        "confidence", "created_at",
    ],
    "brain_packet_evidence": [
        "evidence_id", "packet_id", "chunk_id", "evidence_role",
        "confidence", "created_at",
    ],
    "brain_relationships": [
        "relationship_id", "source_packet_id", "target_packet_id",
        "predicate", "evidence_count", "confidence", "metadata",
        "created_at",
    ],
    "brain_validation_samples": [
        "sample_id", "packet_id", "verdict", "reviewed_by",
        "reviewed_at", "notes", "metrics",
    ],
}

# JSON columns that need serialisation before DuckDB insert
_JSON_COLUMNS = {"metadata", "input_scope", "metrics"}


class BrainConnector:
    """Read-only connector: PostgreSQL Brain → DuckDB analytics.

    Loads Brain tables into DuckDB for fast columnar queries.
    Every load operation is logged for audit.
    """

    def __init__(self, duckdb_conn: Any) -> None:
        self._conn = duckdb_conn
        self._load_log: list[dict] = []

    def init_brain_tables(self) -> None:
        """Create Brain table schemas in DuckDB."""
        for table_name, ddl in BRAIN_TABLES.items():
            self._conn.execute(ddl)
        log.info("Brain tables initialised in DuckDB: %s", list(BRAIN_TABLES.keys()))

    async def load_from_postgres(self, tables: list[str] | None = None) -> dict[str, int]:
        """Load Brain tables from PostgreSQL into DuckDB.

        Args:
            tables: specific tables to load (default: all)

        Returns:
            dict mapping table name to row count loaded
        """
        import asyncpg

        dsn = _get_dsn()
        conn = await asyncpg.connect(dsn)
        try:
            target_tables = tables or list(BRAIN_TABLES.keys())
            counts: dict[str, int] = {}

            for table in target_tables:
                if table not in BRAIN_TABLES:
                    log.warning("Unknown Brain table: %s — skipping", table)
                    continue

                columns = _BRAIN_COLUMNS[table]
                col_list = ", ".join(columns)
                query = f"SELECT {col_list} FROM {table}"

                rows = await conn.fetch(query)

                # Clear existing data
                self._conn.execute(f"DELETE FROM {table}")

                # Insert rows
                placeholders = ", ".join(["?"] * len(columns))
                insert_sql = f"INSERT INTO {table} VALUES ({placeholders})"

                for row in rows:
                    values = []
                    for col in columns:
                        val = row[col]
                        # Serialise JSON/dict columns
                        if col in _JSON_COLUMNS and val is not None:
                            val = json.dumps(dict(val)) if hasattr(val, "items") else str(val)
                        # Convert UUID to string
                        if hasattr(val, "hex"):
                            val = str(val)
                        values.append(val)
                    self._conn.execute(insert_sql, values)

                count = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                counts[table] = count
                log.info("Loaded %d rows from Brain.%s", count, table)

            # Log the load
            self._load_log.append({
                "loaded_at": datetime.now(timezone.utc).isoformat(),
                "tables": counts,
                "total_rows": sum(counts.values()),
            })

            return counts
        finally:
            await conn.close()

    def load_from_parquet(self, parquet_dir: Path) -> dict[str, int]:
        """Load Brain tables from Parquet files.

        Expected files: brain_packets.parquet, brain_documents.parquet, etc.
        This is the production path — nightly cron exports Postgres → Parquet.
        """
        counts: dict[str, int] = {}
        for table in BRAIN_TABLES:
            parquet_file = parquet_dir / f"{table}.parquet"
            if not parquet_file.exists():
                log.debug("No Parquet file for %s — skipping", table)
                continue

            self._conn.execute(f"DELETE FROM {table}")
            self._conn.execute(
                f"INSERT INTO {table} SELECT * FROM read_parquet('{parquet_file}')"
            )
            count = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            counts[table] = count
            log.info("Loaded %d rows from %s", count, parquet_file)

        self._load_log.append({
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "source": "parquet",
            "tables": counts,
            "total_rows": sum(counts.values()),
        })
        return counts

    def export_to_parquet(self, output_dir: Path) -> dict[str, int]:
        """Export Brain tables from DuckDB to Parquet files.

        This is the nightly snapshot script's core operation.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        counts: dict[str, int] = {}

        for table in BRAIN_TABLES:
            count = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if count == 0:
                continue
            output_file = output_dir / f"{table}.parquet"
            self._conn.execute(
                f"COPY {table} TO '{output_file}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            counts[table] = count
            log.info("Exported %d rows to %s", count, output_file)

        return counts

    def get_load_log(self) -> list[dict]:
        """Return the load operation audit log."""
        return list(self._load_log)


# ---------------------------------------------------------------------------
# Standalone Parquet export (for cron/systemd)
# ---------------------------------------------------------------------------


async def export_brain_to_parquet(output_dir: str | Path) -> dict[str, int]:
    """Export Brain PostgreSQL tables to Parquet for DuckDB consumption.

    Usage (cron): python -m vellum.analytics.brain_connector /opt/amplified/data/brain_snapshots/
    """
    try:
        import duckdb
    except ImportError:
        raise RuntimeError("DuckDB required for Parquet export — pip install duckdb")

    output_path = Path(output_dir)
    conn = duckdb.connect(":memory:")

    try:
        connector = BrainConnector(conn)
        connector.init_brain_tables()

        # Load from Postgres
        counts = await connector.load_from_postgres()
        log.info("Loaded %d total rows from Brain PostgreSQL", sum(counts.values()))

        # Export to Parquet
        export_counts = connector.export_to_parquet(output_path)
        log.info("Exported Brain snapshot to %s: %s", output_path, export_counts)

        return export_counts
    finally:
        conn.close()


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m vellum.analytics.brain_connector <output_dir>")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    asyncio.run(export_brain_to_parquet(sys.argv[1]))
