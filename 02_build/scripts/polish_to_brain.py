#!/usr/bin/env python3
"""
Visual Polish → Brain Postgres Sync
=====================================
Reads completed experiment data from the Visual Polish SQLite database
and syncs it into the amplified_brain PostgreSQL database.

Idempotent: uses ON CONFLICT DO UPDATE for safe re-runs.

Usage:
    python polish_to_brain.py [--sqlite-path PATH] [--dry-run]

Environment:
    POLISH_SQLITE_PATH  — Path to Visual Polish SQLite database
    BRAIN_DSN           — PostgreSQL DSN for amplified_brain
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD — individual connection params

Devon-a81b | 2026-05-09 | AMP-280 polish-to-brain sync script
"""

import argparse
import asyncio
import json
import logging
import os
import sqlite3
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("polish-to-brain")

DEFAULT_SQLITE_PATH = "/opt/amplified/polish-pipeline/polish.db"


def get_dsn() -> str:
    if dsn := os.environ.get("BRAIN_DSN"):
        return dsn
    host = os.environ.get("DB_HOST", "cove-postgres")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "amplified_brain")
    user = os.environ.get("DB_USER", "brain_writer")
    password = os.environ.get("DB_PASSWORD", "")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def read_sqlite(db_path: str) -> dict:
    """Read all 6 tables from the Visual Polish SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    tables = {}
    for table in ["experiment_runs", "variants", "screenshots",
                  "hard_check_results", "aesthetic_scores", "polish_scores"]:
        try:
            cur.execute(f"SELECT * FROM {table}")
            tables[table] = [dict(row) for row in cur.fetchall()]
            logger.info(f"  {table}: {len(tables[table])} rows")
        except sqlite3.OperationalError as e:
            logger.warning(f"  {table}: skipped ({e})")
            tables[table] = []

    conn.close()
    return tables


async def ensure_tables(conn: asyncpg.Connection):
    """Create polish sync tables if they don't exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS polish_experiment_runs (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL,
            trigger TEXT NOT NULL,
            target_dimension TEXT,
            category TEXT NOT NULL,
            baseline_score REAL,
            status TEXT NOT NULL,
            decision TEXT,
            decided_by TEXT,
            decided_at TIMESTAMPTZ,
            notes TEXT,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS polish_variants (
            id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL REFERENCES polish_experiment_runs(id),
            deltas_json JSONB NOT NULL,
            generated_by TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS polish_screenshots (
            id TEXT PRIMARY KEY,
            variant_id TEXT NOT NULL REFERENCES polish_variants(id),
            view_id TEXT NOT NULL,
            viewport_width INTEGER,
            viewport_height INTEGER,
            file_path TEXT NOT NULL,
            captured_at TIMESTAMPTZ NOT NULL,
            render_duration_ms INTEGER,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS polish_hard_check_results (
            id TEXT PRIMARY KEY,
            variant_id TEXT NOT NULL REFERENCES polish_variants(id),
            rule_id TEXT NOT NULL,
            passed BOOLEAN NOT NULL,
            violations_json JSONB,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS polish_aesthetic_scores (
            id TEXT PRIMARY KEY,
            variant_id TEXT NOT NULL REFERENCES polish_variants(id),
            view_id TEXT NOT NULL,
            scorer TEXT NOT NULL,
            dimension TEXT,
            score REAL NOT NULL,
            rationale TEXT,
            scored_at TIMESTAMPTZ NOT NULL,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS polish_scores (
            id TEXT PRIMARY KEY,
            variant_id TEXT NOT NULL REFERENCES polish_variants(id),
            uiclip_score REAL,
            rubric_weighted_total REAL,
            composite_score REAL NOT NULL,
            visual_regression_diff_percent REAL,
            dimension_deltas_json JSONB,
            computed_at TIMESTAMPTZ NOT NULL,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


async def sync_experiment_runs(conn: asyncpg.Connection, rows: list) -> int:
    count = 0
    for row in rows:
        await conn.execute("""
            INSERT INTO polish_experiment_runs
                (id, created_at, trigger, target_dimension, category, baseline_score,
                 status, decision, decided_by, decided_at, notes)
            VALUES ($1, $2::timestamptz, $3, $4, $5, $6, $7, $8, $9, $10::timestamptz, $11)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                decision = EXCLUDED.decision,
                decided_by = EXCLUDED.decided_by,
                decided_at = EXCLUDED.decided_at,
                notes = EXCLUDED.notes,
                synced_at = now()
        """, row["id"], row["created_at"], row["trigger"], row.get("target_dimension"),
            row["category"], row.get("baseline_score"), row["status"],
            row.get("decision"), row.get("decided_by"), row.get("decided_at"), row.get("notes"))
        count += 1
    return count


async def sync_variants(conn: asyncpg.Connection, rows: list) -> int:
    count = 0
    for row in rows:
        deltas = row.get("deltas_json", "[]")
        if isinstance(deltas, str):
            deltas = json.loads(deltas) if deltas else []
        await conn.execute("""
            INSERT INTO polish_variants (id, experiment_id, deltas_json, generated_by, created_at)
            VALUES ($1, $2, $3::jsonb, $4, $5::timestamptz)
            ON CONFLICT (id) DO UPDATE SET
                deltas_json = EXCLUDED.deltas_json,
                synced_at = now()
        """, row["id"], row["experiment_id"], json.dumps(deltas),
            row["generated_by"], row["created_at"])
        count += 1
    return count


async def sync_screenshots(conn: asyncpg.Connection, rows: list) -> int:
    count = 0
    for row in rows:
        await conn.execute("""
            INSERT INTO polish_screenshots
                (id, variant_id, view_id, viewport_width, viewport_height,
                 file_path, captured_at, render_duration_ms)
            VALUES ($1, $2, $3, $4, $5, $6, $7::timestamptz, $8)
            ON CONFLICT (id) DO NOTHING
        """, row["id"], row["variant_id"], row["view_id"],
            row.get("viewport_width"), row.get("viewport_height"),
            row["file_path"], row["captured_at"], row.get("render_duration_ms"))
        count += 1
    return count


async def sync_hard_checks(conn: asyncpg.Connection, rows: list) -> int:
    count = 0
    for row in rows:
        violations = row.get("violations_json")
        if isinstance(violations, str):
            violations = json.loads(violations) if violations else None
        await conn.execute("""
            INSERT INTO polish_hard_check_results (id, variant_id, rule_id, passed, violations_json)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            ON CONFLICT (id) DO NOTHING
        """, row["id"], row["variant_id"], row["rule_id"],
            bool(row["passed"]), json.dumps(violations) if violations else None)
        count += 1
    return count


async def sync_aesthetic_scores(conn: asyncpg.Connection, rows: list) -> int:
    count = 0
    for row in rows:
        await conn.execute("""
            INSERT INTO polish_aesthetic_scores
                (id, variant_id, view_id, scorer, dimension, score, rationale, scored_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::timestamptz)
            ON CONFLICT (id) DO NOTHING
        """, row["id"], row["variant_id"], row["view_id"],
            row["scorer"], row.get("dimension"), float(row["score"]),
            row.get("rationale"), row["scored_at"])
        count += 1
    return count


async def sync_polish_scores(conn: asyncpg.Connection, rows: list) -> int:
    count = 0
    for row in rows:
        deltas = row.get("dimension_deltas_json")
        if isinstance(deltas, str):
            deltas = json.loads(deltas) if deltas else None
        await conn.execute("""
            INSERT INTO polish_scores
                (id, variant_id, uiclip_score, rubric_weighted_total,
                 composite_score, visual_regression_diff_percent, dimension_deltas_json, computed_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::timestamptz)
            ON CONFLICT (id) DO UPDATE SET
                composite_score = EXCLUDED.composite_score,
                synced_at = now()
        """, row["id"], row["variant_id"], row.get("uiclip_score"),
            row.get("rubric_weighted_total"), float(row["composite_score"]),
            row.get("visual_regression_diff_percent"),
            json.dumps(deltas) if deltas else None, row["computed_at"])
        count += 1
    return count


async def run_sync(sqlite_path: str, dry_run: bool = False):
    logger.info(f"Reading SQLite: {sqlite_path}")
    if not Path(sqlite_path).exists():
        logger.error(f"SQLite database not found: {sqlite_path}")
        return

    tables = read_sqlite(sqlite_path)
    total = sum(len(v) for v in tables.values())
    logger.info(f"Total rows to sync: {total}")

    if dry_run:
        logger.info("DRY RUN — no writes performed")
        return

    dsn = get_dsn()
    logger.info(f"Connecting to PostgreSQL...")
    conn = await asyncpg.connect(dsn)

    try:
        await ensure_tables(conn)
        logger.info("Tables ensured.")

        counts = {}
        counts["experiment_runs"] = await sync_experiment_runs(conn, tables["experiment_runs"])
        counts["variants"] = await sync_variants(conn, tables["variants"])
        counts["screenshots"] = await sync_screenshots(conn, tables["screenshots"])
        counts["hard_check_results"] = await sync_hard_checks(conn, tables["hard_check_results"])
        counts["aesthetic_scores"] = await sync_aesthetic_scores(conn, tables["aesthetic_scores"])
        counts["polish_scores"] = await sync_polish_scores(conn, tables["polish_scores"])

        logger.info("Sync complete:")
        for table, count in counts.items():
            logger.info(f"  {table}: {count} rows synced")
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Sync Visual Polish SQLite → Brain Postgres")
    parser.add_argument("--sqlite-path", default=os.environ.get("POLISH_SQLITE_PATH", DEFAULT_SQLITE_PATH),
                        help="Path to Visual Polish SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Read SQLite but don't write to Postgres")
    args = parser.parse_args()
    asyncio.run(run_sync(args.sqlite_path, args.dry_run))


if __name__ == "__main__":
    main()
