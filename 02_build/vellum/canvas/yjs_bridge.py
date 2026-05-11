"""Yjs document wrapper using pycrdt (Python bindings for yrs/Yjs).

Manages a Y.Doc per sheet. Each doc contains a Y.Array named "entries"
that stores serialised SheetEntry dicts. The bridge provides the
collaboration-ready CRDT layer that all Vellum modes build on.

Signed-by: Devon-8c5f | 2026-05-11 | AMP-324
"""

from __future__ import annotations

from typing import Any

import pycrdt

from vellum.models.entry import SheetEntry


class YjsBridge:
    """Per-sheet Yjs document manager backed by pycrdt."""

    def __init__(self) -> None:
        self._docs: dict[str, pycrdt.Doc] = {}

    async def create_doc(self, sheet_id: str) -> pycrdt.Doc:
        """Create a new Y.Doc for *sheet_id*.

        Returns the doc (also cached internally). Raises ValueError
        if a doc already exists for this sheet.
        """
        if sheet_id in self._docs:
            raise ValueError(f"Doc already exists for sheet {sheet_id}")
        doc: pycrdt.Doc = pycrdt.Doc()
        doc["entries"] = pycrdt.Array()
        self._docs[sheet_id] = doc
        return doc

    async def get_or_create_doc(self, sheet_id: str) -> pycrdt.Doc:
        """Return the existing doc or lazily create one."""
        if sheet_id not in self._docs:
            return await self.create_doc(sheet_id)
        return self._docs[sheet_id]

    async def append_entry(self, sheet_id: str, entry: SheetEntry) -> None:
        """Append a SheetEntry to the Y.Array inside the sheet's doc.

        The entry is stored as a JSON-serialisable dict so that
        downstream Yjs peers can decode it without Pydantic.
        """
        doc = await self.get_or_create_doc(sheet_id)
        entries_array: pycrdt.Array = doc["entries"]
        entries_array.append(entry.model_dump(mode="json"))

    async def get_entries(self, sheet_id: str) -> list[dict[str, Any]]:
        """Return all entries for *sheet_id* as plain dicts.

        Returns an empty list if the doc does not exist.
        """
        if sheet_id not in self._docs:
            return []
        doc = self._docs[sheet_id]
        entries_array: pycrdt.Array = doc["entries"]
        return list(entries_array)

    async def get_doc_state(self, sheet_id: str) -> bytes:
        """Return the Yjs binary state vector for *sheet_id*.

        This is the payload a connecting peer needs in order to sync.
        Raises KeyError if the doc does not exist.
        """
        if sheet_id not in self._docs:
            raise KeyError(f"No doc for sheet {sheet_id}")
        doc = self._docs[sheet_id]
        return doc.get_state()

    async def apply_update(self, sheet_id: str, update: bytes) -> None:
        """Apply a binary Yjs update from a remote peer."""
        if sheet_id not in self._docs:
            raise KeyError(f"No doc for sheet {sheet_id}")
        doc = self._docs[sheet_id]
        doc.apply_update(update)

    async def remove_doc(self, sheet_id: str) -> None:
        """Remove a cached doc (e.g. on sheet archive)."""
        self._docs.pop(sheet_id, None)
