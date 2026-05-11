"""Additive-only write enforcement for Vellum sheets.

Core invariant: no deletes, no overwrites. A strikethrough is a new
event, not destruction. This guard is checked before every write to
ensure the append-only contract holds.

Signed-by: Devon-8c5f | 2026-05-11 | AMP-324
"""

from __future__ import annotations

from vellum.models.entry import SheetEntry


class AdditiveGuard:
    """Validates that new writes do not violate the additive-only rule."""

    @staticmethod
    async def validate_write(
        new_entry: SheetEntry,
        existing_entries: list[SheetEntry],
    ) -> bool:
        """Return True if *new_entry* is a valid additive write.

        Rejection criteria (any one → False):
        - new_entry.id matches an existing entry id (duplicate / overwrite)
        - new_entry.content matches an existing entry's content AND
          new_entry.entry_type is the same (exact duplicate payload)
        - new_entry.sheet_id differs from existing entries (cross-sheet
          injection attempt)

        An empty existing list always passes (first write is always valid).
        """
        if not existing_entries:
            return True

        expected_sheet = existing_entries[0].sheet_id
        if new_entry.sheet_id != expected_sheet:
            return False

        for existing in existing_entries:
            if new_entry.id == existing.id:
                return False
            if (
                new_entry.content == existing.content
                and new_entry.entry_type == existing.entry_type
            ):
                return False

        return True

    @staticmethod
    async def validate_batch(
        new_entries: list[SheetEntry],
        existing_entries: list[SheetEntry],
    ) -> bool:
        """Validate a batch of new entries against existing state.

        Each entry is checked incrementally: earlier entries in the
        batch become part of the "existing" set for later ones.
        """
        combined = list(existing_entries)
        for entry in new_entries:
            if not await AdditiveGuard.validate_write(entry, combined):
                return False
            combined.append(entry)
        return True
