"""
SQLite-backed checkpoint — per-item, per-stage state tracker.

Provides crash-safe resumability. Each file gets a row; each stage transition
is an UPDATE. On resume, the orchestrator queries for items that haven't
reached the terminal stage and picks up where it left off.

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .models import Classification, ItemStatus, PipelineItem, PuddingTaxonomy


class CheckpointStore:
    """SQLite checkpoint for pipeline state."""

    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_items (
                    file_path   TEXT PRIMARY KEY,
                    file_hash   TEXT NOT NULL DEFAULT '',
                    stage       TEXT NOT NULL DEFAULT 'pending',
                    taxonomy    TEXT,
                    classification TEXT,
                    error       TEXT,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stage ON pipeline_items(stage)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS run_meta (
                    run_id      TEXT PRIMARY KEY,
                    started_at  TEXT NOT NULL,
                    finished_at TEXT,
                    config      TEXT
                )
            """)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def register_items(self, file_paths: list[str]) -> int:
        """Register files for processing. Returns count of newly registered items."""
        now = datetime.now(timezone.utc).isoformat()
        added = 0
        with self._conn() as conn:
            for fp in file_paths:
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO pipeline_items
                           (file_path, stage, created_at, updated_at)
                           VALUES (?, ?, ?, ?)""",
                        (fp, ItemStatus.PENDING.value, now, now),
                    )
                    added += conn.total_changes  # approximation
                except sqlite3.IntegrityError:
                    pass
            added = conn.execute(
                "SELECT changes()"
            ).fetchone()[0]
        return added

    def update_item(
        self,
        file_path: str,
        stage: ItemStatus,
        file_hash: str = "",
        taxonomy: Optional[PuddingTaxonomy] = None,
        classification: Optional[Classification] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update a single item's state."""
        now = datetime.now(timezone.utc).isoformat()
        tax_json = taxonomy.model_dump_json() if taxonomy else None
        cls_json = classification.model_dump_json() if classification else None
        with self._conn() as conn:
            conn.execute(
                """UPDATE pipeline_items
                   SET stage=?, file_hash=?, taxonomy=?, classification=?,
                       error=?, updated_at=?
                   WHERE file_path=?""",
                (stage.value, file_hash, tax_json, cls_json, error, now, file_path),
            )

    def get_items_by_stage(self, stage: ItemStatus, limit: int = 0) -> list[PipelineItem]:
        """Retrieve items at a given stage."""
        with self._conn() as conn:
            query = "SELECT * FROM pipeline_items WHERE stage=?"
            params: list = [stage.value]
            if limit > 0:
                query += " LIMIT ?"
                params.append(limit)
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_item(self, file_path: str) -> Optional[PipelineItem]:
        """Retrieve a single item by path."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pipeline_items WHERE file_path=?", (file_path,)
            ).fetchone()
        return self._row_to_item(row) if row else None

    def count_by_stage(self) -> dict[str, int]:
        """Return counts grouped by stage."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT stage, COUNT(*) FROM pipeline_items GROUP BY stage"
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def total_count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM pipeline_items").fetchone()[0]

    def record_run_start(self, run_id: str, config: Optional[dict] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO run_meta (run_id, started_at, config) VALUES (?, ?, ?)",
                (run_id, now, json.dumps(config) if config else None),
            )

    def record_run_end(self, run_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE run_meta SET finished_at=? WHERE run_id=?", (now, run_id)
            )

    @staticmethod
    def _row_to_item(row: tuple) -> PipelineItem:
        file_path, file_hash, stage, taxonomy, classification, error, created_at, updated_at = row
        tax = PuddingTaxonomy.model_validate_json(taxonomy) if taxonomy else None
        cls = Classification.model_validate_json(classification) if classification else None
        return PipelineItem(
            file_path=file_path,
            file_hash=file_hash or "",
            stage=ItemStatus(stage),
            taxonomy=tax,
            classification=cls,
            error=error,
            created_at=created_at,
            updated_at=updated_at,
        )
