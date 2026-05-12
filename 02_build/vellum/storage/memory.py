"""In-memory storage backend for Vellum — dev and testing.

Same interface as PostgresSheetStore but everything lives in dicts.
Data is lost on process restart. Use for local dev and pytest only.

Scaffold (Devon-3397) | 2026-05-11
"""

from __future__ import annotations

from vellum.models.entry import SheetEntry
from vellum.models.sheet import Sheet, SheetMeta
from vellum.models.token import ShareToken


class MemorySheetStore:
    """In-memory implementation of the SheetStore protocol."""

    def __init__(self) -> None:
        self._sheets: dict[str, Sheet] = {}
        self._tenant_index: dict[str, set[str]] = {}
        self._tokens: dict[str, ShareToken] = {}

    async def create_sheet(self, tenant_id: str, meta: SheetMeta) -> Sheet:
        sheet = Sheet(meta=meta)
        self._sheets[meta.id] = sheet
        self._tenant_index.setdefault(tenant_id, set()).add(meta.id)
        return sheet

    async def get_sheet(self, tenant_id: str, sheet_id: str) -> Sheet | None:
        sheet = self._sheets.get(sheet_id)
        if sheet is None or sheet.meta.tenant_id != tenant_id:
            return None
        return sheet

    async def get_sheet_by_id(self, sheet_id: str) -> Sheet | None:
        return self._sheets.get(sheet_id)

    async def list_sheets(self, tenant_id: str) -> list[Sheet]:
        sheet_ids = self._tenant_index.get(tenant_id, set())
        return [self._sheets[sid] for sid in sheet_ids if sid in self._sheets]

    async def append_entry(self, sheet_id: str, entry: SheetEntry) -> None:
        sheet = self._sheets.get(sheet_id)
        if sheet is None:
            raise KeyError(f"Sheet {sheet_id} not found")
        sheet.entries.append(entry)
        sheet.latest_hash = entry.entry_hash

    async def store_token(self, token: ShareToken) -> None:
        self._tokens[token.token_id] = token

    async def get_token(self, token_id: str) -> ShareToken | None:
        return self._tokens.get(token_id)

    async def revoke_token(self, token_id: str) -> None:
        token = self._tokens.get(token_id)
        if token is not None:
            token.revoked = True

    async def close(self) -> None:
        pass

    def clear(self) -> None:
        """Reset all stores — for testing."""
        self._sheets.clear()
        self._tenant_index.clear()
        self._tokens.clear()
