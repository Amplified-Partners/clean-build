"""Vellum integration — read sheets, write entries.

In test mode, uses the in-memory store directly.
In production, calls Vellum's REST API.

Dana | 2026-05-20 | From Computer's Loom spec §2.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from loom.findings import Finding

log = logging.getLogger("loom.integrations.vellum")


class VellumClient:
    """Adapter for reading/writing Vellum sheets.

    Uses the in-memory store for testing and local dev.
    Production swaps to HTTP client.
    """

    def __init__(self, use_store: bool = True) -> None:
        self._use_store = use_store

    async def write_entry(self, sheet_title: str, entry_data: dict) -> str:
        """Write an entry to a named Vellum sheet.

        If the sheet doesn't exist, creates it (telemetry mode).
        Returns the entry hash for chaining.
        """
        from vellum.models.entry import SheetEntry
        from vellum.models.sheet import SheetMeta
        from vellum.storage import get_store

        store = get_store()
        sheets = await store.list_sheets("ewan")

        # Find sheet by title
        target = None
        for s in sheets:
            if s.meta.title == sheet_title:
                target = s
                break

        # Auto-create if not found
        if target is None:
            meta = SheetMeta(
                title=sheet_title,
                mode="telemetry",
                created_by=entry_data.get("author", "loom"),
            )
            await store.create_sheet(meta)
            target = await store.get_sheet(meta.id)

        entry = SheetEntry(
            sheet_id=target.meta.id,
            author=entry_data.get("author", "loom"),
            content=entry_data.get("content", ""),
            prev_hash=target.latest_hash,
            entry_type=entry_data.get("entry_type", "metric"),
            epistemic_tier=entry_data.get("epistemic_tier",
                                          entry_data.get("epistemic_status", "STRUCTURED")),
            metadata=entry_data.get("metadata", {}),
        )
        await store.append_entry(target.meta.id, entry)
        log.info("Wrote entry to %s: %s", sheet_title, entry.entry_hash[:12])
        return entry.entry_hash

    async def read_recent_entries(
        self, sheet_title: str, hours: int = 24
    ) -> list[dict]:
        """Read entries from the last N hours on a sheet."""
        from vellum.storage import get_store

        store = get_store()
        sheets = await store.list_sheets("ewan")

        cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)

        for s in sheets:
            if s.meta.title == sheet_title:
                return [
                    {
                        "id": e.id,
                        "author": e.author,
                        "content": e.content,
                        "entry_type": e.entry_type,
                        "epistemic_tier": e.epistemic_tier,
                        "timestamp": e.timestamp.isoformat(),
                        "metadata": e.metadata,
                    }
                    for e in s.entries
                    if e.timestamp.timestamp() > cutoff
                ]
        return []

    async def load_baselines(self, sheet_title: str) -> dict:
        """Load baseline values from the most recent baseline entry on a sheet."""
        entries = await self.read_recent_entries(sheet_title, hours=168)  # 7 days
        for entry in reversed(entries):
            if entry.get("metadata", {}).get("is_baseline"):
                return entry["metadata"].get("baselines", {})
        # Default baselines if none recorded
        return {
            "triangulation": 0.8,
            "contradiction_delta": 5,
        }
