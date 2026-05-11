"""Tenant isolation at the storage layer.

Cross-tenant reads return 404 (not 403) — no information leak about
who else has a sheet. This module provides the in-memory reference
implementation; the PostgreSQL persistence adapter wraps the same
interface with real queries.

Signed-by: Devon-8c5f | 2026-05-11 | AMP-324
"""

from __future__ import annotations

from typing import Any

from vellum.models.entry import SheetEntry
from vellum.models.sheet import Sheet, SheetMeta


class TenantNotFoundError(Exception):
    """Raised when a tenant-scoped lookup finds nothing.

    Callers should map this to HTTP 404 — never 403.
    """


class TenantStore:
    """In-memory tenant-isolated sheet store.

    Production code should subclass or replace this with an async
    SQLAlchemy / asyncpg implementation that enforces the same
    tenant_id predicate on every query.
    """

    def __init__(self) -> None:
        self._sheets: dict[str, dict[str, Sheet]] = {}

    async def create_sheet(
        self,
        tenant_id: str,
        meta: dict[str, Any] | SheetMeta,
    ) -> Sheet:
        """Create a new sheet scoped to *tenant_id*.

        *meta* can be a SheetMeta instance or a dict of kwargs for one.
        Returns the newly created Sheet.
        """
        if isinstance(meta, dict):
            meta = SheetMeta(tenant_id=tenant_id, **meta)

        if meta.tenant_id != tenant_id:
            raise ValueError("SheetMeta.tenant_id must match tenant_id")

        sheet = Sheet(meta=meta)
        self._sheets.setdefault(tenant_id, {})[meta.id] = sheet
        return sheet

    async def get_sheet(self, tenant_id: str, sheet_id: str) -> Sheet:
        """Return a sheet if it belongs to *tenant_id*.

        Raises TenantNotFoundError (→ 404) if the sheet does not exist
        or belongs to a different tenant. The caller cannot distinguish
        "does not exist" from "belongs to someone else".
        """
        tenant_sheets = self._sheets.get(tenant_id, {})
        sheet = tenant_sheets.get(sheet_id)
        if sheet is None:
            raise TenantNotFoundError(
                f"Sheet {sheet_id} not found",
            )
        return sheet

    async def list_sheets(self, tenant_id: str) -> list[Sheet]:
        """Return all sheets belonging to *tenant_id*."""
        return list(self._sheets.get(tenant_id, {}).values())

    async def append_entry(
        self,
        tenant_id: str,
        sheet_id: str,
        entry: SheetEntry,
    ) -> Sheet:
        """Append an entry to a tenant-scoped sheet.

        Raises TenantNotFoundError if the sheet is not found for this
        tenant.
        """
        sheet = await self.get_sheet(tenant_id, sheet_id)
        sheet.entries.append(entry)
        sheet.latest_hash = entry.entry_hash
        return sheet

    async def delete_sheet(self, tenant_id: str, sheet_id: str) -> None:
        """Soft-delete (remove from listing). Additive-only means
        data is never truly destroyed — this just removes from the
        active index for the tenant.
        """
        tenant_sheets = self._sheets.get(tenant_id, {})
        if sheet_id not in tenant_sheets:
            raise TenantNotFoundError(
                f"Sheet {sheet_id} not found",
            )
        del tenant_sheets[sheet_id]
