"""In-memory storage backend — dev and testing.

Enforces mode/entry-type isolation (§2.3) and supports durable
token revocation (§3.1) within the process lifetime.

Devon-b5dc | 2026-05-14
Hardened by Dana | 2026-05-20 | §2.3 mode guard, §3.1 revoke_token
"""

from __future__ import annotations

from datetime import datetime, timezone

from vellum.canvas.mode_guard import validate_mode_entry_type
from vellum.models.entry import SheetEntry
from vellum.models.sheet import Sheet, SheetMeta
from vellum.models.token import ShareToken


class MemorySheetStore:

    def __init__(self) -> None:
        self._sheets: dict[str, Sheet] = {}
        self._tokens: dict[str, ShareToken] = {}

    async def create_sheet(self, meta: SheetMeta) -> Sheet:
        sheet = Sheet(meta=meta)
        self._sheets[meta.id] = sheet
        return sheet

    async def get_sheet(self, sheet_id: str) -> Sheet | None:
        return self._sheets.get(sheet_id)

    async def list_sheets(self, tenant_id: str) -> list[Sheet]:
        return [
            s for s in self._sheets.values()
            if s.meta.tenant_id == tenant_id
        ]

    async def append_entry(self, sheet_id: str, entry: SheetEntry) -> None:
        """Append an entry. Enforces mode/entry-type isolation (§2.3)."""
        sheet = self._sheets.get(sheet_id)
        if sheet is None:
            raise KeyError(f"Sheet {sheet_id} not found")
        # §2.3: reject entry types that don't belong to this sheet's mode
        validate_mode_entry_type(sheet.meta.mode, entry.entry_type)
        sheet.entries.append(entry)
        sheet.latest_hash = entry.entry_hash

    async def store_token(self, token: ShareToken) -> None:
        self._tokens[token.token_id] = token

    async def get_token(self, token_id: str) -> ShareToken | None:
        return self._tokens.get(token_id)

    async def revoke_token(self, token_id: str, revoked_by: str) -> None:
        """Revoke a token with attribution and timestamp (§3.1)."""
        token = self._tokens.get(token_id)
        if token is None:
            raise KeyError(f"Token {token_id} not found")
        token.revoked = True
        token.revoked_at = datetime.now(timezone.utc)
        token.revoked_by = revoked_by

    async def get_decisions(self, tenant_id: str) -> list[SheetEntry]:
        decisions = []
        for sheet in self._sheets.values():
            if sheet.meta.tenant_id != tenant_id:
                continue
            for entry in sheet.entries:
                if entry.entry_type == "decision":
                    decisions.append(entry)
        decisions.sort(key=lambda e: e.timestamp, reverse=True)
        return decisions

    async def get_unread(
        self,
        tenant_id: str,
        reader_id: str | None = None,
    ) -> list[SheetEntry]:
        unread = []
        for sheet in self._sheets.values():
            if sheet.meta.tenant_id != tenant_id:
                continue

            last_read_timestamp = None
            for entry in sheet.entries:
                if entry.entry_type != "read_receipt":
                    continue
                if reader_id is not None and entry.author != reader_id:
                    continue
                if (
                    last_read_timestamp is None
                    or entry.timestamp > last_read_timestamp
                ):
                    last_read_timestamp = entry.timestamp

            for entry in sheet.entries:
                if entry.entry_type != "agent_write":
                    continue
                if (
                    last_read_timestamp is None
                    or entry.timestamp > last_read_timestamp
                ):
                    unread.append(entry)
        return unread

    async def close(self) -> None:
        pass

    def clear(self) -> None:
        self._sheets.clear()
        self._tokens.clear()
