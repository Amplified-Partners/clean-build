"""
Dead Letter Queue — structured failure handling with retry.

Failed items land here with full context. The CLI can list, inspect, and
retry items from the DLQ. Backed by the same SQLite checkpoint DB.

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


class DLQEntry:
    __slots__ = ("file_path", "stage", "error", "attempts", "last_attempt", "context")

    def __init__(
        self,
        file_path: str,
        stage: str,
        error: str,
        attempts: int = 1,
        last_attempt: str = "",
        context: Optional[dict] = None,
    ):
        self.file_path = file_path
        self.stage = stage
        self.error = error
        self.attempts = attempts
        self.last_attempt = last_attempt or datetime.now(timezone.utc).isoformat()
        self.context = context or {}


class DeadLetterQueue:
    """SQLite-backed DLQ for pipeline failures."""

    MAX_RETRIES = 3

    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dlq (
                    file_path    TEXT PRIMARY KEY,
                    stage        TEXT NOT NULL,
                    error        TEXT NOT NULL,
                    attempts     INTEGER NOT NULL DEFAULT 1,
                    last_attempt TEXT NOT NULL,
                    context      TEXT
                )
            """)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add(self, file_path: str, stage: str, error: str, context: Optional[dict] = None) -> None:
        """Add or update a DLQ entry. Increments attempt count on duplicates."""
        now = datetime.now(timezone.utc).isoformat()
        ctx = json.dumps(context) if context else None
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT attempts FROM dlq WHERE file_path=?", (file_path,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE dlq SET stage=?, error=?, attempts=?, last_attempt=?, context=?
                       WHERE file_path=?""",
                    (stage, error, existing[0] + 1, now, ctx, file_path),
                )
            else:
                conn.execute(
                    "INSERT INTO dlq (file_path, stage, error, attempts, last_attempt, context) VALUES (?,?,?,?,?,?)",
                    (file_path, stage, error, 1, now, ctx),
                )

    def get_retryable(self, max_retries: Optional[int] = None) -> list[DLQEntry]:
        """Return entries that haven't exceeded the retry limit."""
        limit = max_retries or self.MAX_RETRIES
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM dlq WHERE attempts <= ? ORDER BY last_attempt ASC",
                (limit,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_all(self) -> list[DLQEntry]:
        """Return all DLQ entries."""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM dlq ORDER BY last_attempt DESC").fetchall()
        return [self._row_to_entry(r) for r in rows]

    def remove(self, file_path: str) -> None:
        """Remove an entry after successful retry."""
        with self._conn() as conn:
            conn.execute("DELETE FROM dlq WHERE file_path=?", (file_path,))

    def count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM dlq").fetchone()[0]

    def clear(self) -> int:
        """Clear all DLQ entries. Returns count removed."""
        with self._conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM dlq").fetchone()[0]
            conn.execute("DELETE FROM dlq")
        return count

    @staticmethod
    def _row_to_entry(row: tuple) -> DLQEntry:
        file_path, stage, error, attempts, last_attempt, context = row
        ctx = json.loads(context) if context else None
        return DLQEntry(
            file_path=file_path,
            stage=stage,
            error=error,
            attempts=attempts,
            last_attempt=last_attempt,
            context=ctx,
        )
