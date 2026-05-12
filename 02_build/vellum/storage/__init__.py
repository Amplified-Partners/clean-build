"""Vellum storage layer — abstract interface + backend selection.

Provides SheetStore protocol and factory function. Backends:
- MemorySheetStore: in-memory (tests, local dev)
- PostgresSheetStore: PostgreSQL (production on Beast)

Scaffold (Devon-3397) | 2026-05-11
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from vellum.models.entry import SheetEntry
from vellum.models.sheet import Sheet, SheetMeta
from vellum.models.token import ShareToken


@runtime_checkable
class SheetStore(Protocol):
    """Storage interface for Vellum sheets, entries, and tokens."""

    async def create_sheet(self, tenant_id: str, meta: SheetMeta) -> Sheet: ...
    async def get_sheet(self, tenant_id: str, sheet_id: str) -> Sheet | None: ...
    async def get_sheet_by_id(self, sheet_id: str) -> Sheet | None: ...
    async def list_sheets(self, tenant_id: str) -> list[Sheet]: ...
    async def append_entry(self, sheet_id: str, entry: SheetEntry) -> None: ...
    async def store_token(self, token: ShareToken) -> None: ...
    async def get_token(self, token_id: str) -> ShareToken | None: ...
    async def revoke_token(self, token_id: str) -> None: ...
    async def close(self) -> None: ...


# Global store instance — set by app startup
_store: SheetStore | None = None


def get_store() -> SheetStore:
    """Return the active store. Raises if not initialised."""
    if _store is None:
        raise RuntimeError("Store not initialised — call init_store() first")
    return _store


def set_store(store: SheetStore) -> None:
    """Set the global store instance."""
    global _store  # noqa: PLW0603
    _store = store


async def init_store() -> SheetStore:
    """Initialise the store from DATABASE_URL env var.

    If DATABASE_URL is set → PostgreSQL.
    Otherwise → in-memory (dev/test).
    """
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        from vellum.storage.postgres import PostgresSheetStore
        store = PostgresSheetStore(database_url)
        await store.initialise()
    else:
        from vellum.storage.memory import MemorySheetStore
        store = MemorySheetStore()

    set_store(store)
    return store
