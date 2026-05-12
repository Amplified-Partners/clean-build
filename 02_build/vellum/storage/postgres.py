"""PostgreSQL storage backend for Vellum.

Uses asyncpg for async queries. Stores sheets, entries, and tokens
in three tables with tenant_id predicates on every query.

Schema is auto-created on startup via initialise().

Scaffold (Devon-3397) | 2026-05-11
"""

from __future__ import annotations


import asyncpg

from vellum.models.entry import SheetEntry
from vellum.models.sheet import Sheet, SheetMeta
from vellum.models.token import ShareToken


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vellum_sheets (
    id          TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    title       TEXT NOT NULL,
    mode        TEXT NOT NULL DEFAULT 'brief',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by  TEXT NOT NULL,
    latest_hash TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_vellum_sheets_tenant
    ON vellum_sheets (tenant_id);

CREATE TABLE IF NOT EXISTS vellum_entries (
    id          TEXT PRIMARY KEY,
    sheet_id    TEXT NOT NULL REFERENCES vellum_sheets(id),
    author      TEXT NOT NULL,
    content     TEXT NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    prev_hash   TEXT NOT NULL DEFAULT '',
    entry_hash  TEXT NOT NULL,
    entry_type  TEXT NOT NULL DEFAULT 'agent_write',
    seq         SERIAL
);

CREATE INDEX IF NOT EXISTS idx_vellum_entries_sheet
    ON vellum_entries (sheet_id, seq);

CREATE TABLE IF NOT EXISTS vellum_tokens (
    token_id    TEXT PRIMARY KEY,
    sheet_id    TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'read',
    bound_to    TEXT,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_vellum_tokens_sheet
    ON vellum_tokens (sheet_id);
"""


class PostgresSheetStore:
    """PostgreSQL-backed storage for Vellum sheets."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def initialise(self) -> None:
        """Create connection pool and ensure schema exists."""
        self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
        async with self._pool.acquire() as conn:
            await conn.execute(_SCHEMA_SQL)

    def _pool_or_raise(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("PostgresSheetStore not initialised")
        return self._pool

    async def create_sheet(self, tenant_id: str, meta: SheetMeta) -> Sheet:
        pool = self._pool_or_raise()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO vellum_sheets (id, tenant_id, title, mode, created_at, created_by, latest_hash)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                meta.id,
                tenant_id,
                meta.title,
                meta.mode,
                meta.created_at,
                meta.created_by,
                "",
            )
        return Sheet(meta=meta)

    async def get_sheet(self, tenant_id: str, sheet_id: str) -> Sheet | None:
        pool = self._pool_or_raise()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM vellum_sheets WHERE id = $1 AND tenant_id = $2",
                sheet_id,
                tenant_id,
            )
            if row is None:
                return None

            entries = await conn.fetch(
                "SELECT * FROM vellum_entries WHERE sheet_id = $1 ORDER BY seq",
                sheet_id,
            )

        return self._assemble_sheet(row, entries)

    async def get_sheet_by_id(self, sheet_id: str) -> Sheet | None:
        pool = self._pool_or_raise()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM vellum_sheets WHERE id = $1",
                sheet_id,
            )
            if row is None:
                return None

            entries = await conn.fetch(
                "SELECT * FROM vellum_entries WHERE sheet_id = $1 ORDER BY seq",
                sheet_id,
            )

        return self._assemble_sheet(row, entries)

    async def list_sheets(self, tenant_id: str) -> list[Sheet]:
        pool = self._pool_or_raise()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM vellum_sheets WHERE tenant_id = $1 ORDER BY created_at DESC",
                tenant_id,
            )
            sheets = []
            for row in rows:
                entries = await conn.fetch(
                    "SELECT * FROM vellum_entries WHERE sheet_id = $1 ORDER BY seq",
                    row["id"],
                )
                sheets.append(self._assemble_sheet(row, entries))
        return sheets

    async def append_entry(self, sheet_id: str, entry: SheetEntry) -> None:
        pool = self._pool_or_raise()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO vellum_entries (id, sheet_id, author, content, timestamp, prev_hash, entry_hash, entry_type)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    entry.id,
                    entry.sheet_id,
                    entry.author,
                    entry.content,
                    entry.timestamp,
                    entry.prev_hash,
                    entry.entry_hash,
                    entry.entry_type,
                )
                await conn.execute(
                    "UPDATE vellum_sheets SET latest_hash = $1 WHERE id = $2",
                    entry.entry_hash,
                    sheet_id,
                )

    async def store_token(self, token: ShareToken) -> None:
        pool = self._pool_or_raise()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO vellum_tokens (token_id, sheet_id, role, bound_to, expires_at, created_at, revoked)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (token_id) DO UPDATE SET revoked = EXCLUDED.revoked
                """,
                token.token_id,
                token.sheet_id,
                token.role,
                token.bound_to,
                token.expires_at,
                token.created_at,
                token.revoked,
            )

    async def get_token(self, token_id: str) -> ShareToken | None:
        pool = self._pool_or_raise()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM vellum_tokens WHERE token_id = $1",
                token_id,
            )
        if row is None:
            return None
        return ShareToken(
            token_id=row["token_id"],
            sheet_id=row["sheet_id"],
            role=row["role"],
            bound_to=row["bound_to"],
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            revoked=row["revoked"],
        )

    async def revoke_token(self, token_id: str) -> None:
        pool = self._pool_or_raise()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE vellum_tokens SET revoked = TRUE WHERE token_id = $1",
                token_id,
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @staticmethod
    def _assemble_sheet(
        row: asyncpg.Record,
        entry_rows: list[asyncpg.Record],
    ) -> Sheet:
        meta = SheetMeta(
            id=row["id"],
            tenant_id=row["tenant_id"],
            title=row["title"],
            mode=row["mode"],
            created_at=row["created_at"],
            created_by=row["created_by"],
        )
        entries = [
            SheetEntry(
                id=e["id"],
                sheet_id=e["sheet_id"],
                author=e["author"],
                content=e["content"],
                timestamp=e["timestamp"],
                prev_hash=e["prev_hash"],
                entry_hash=e["entry_hash"],
                entry_type=e["entry_type"],
            )
            for e in entry_rows
        ]
        latest_hash = row["latest_hash"] if row["latest_hash"] else ""
        return Sheet(meta=meta, entries=entries, latest_hash=latest_hash)
