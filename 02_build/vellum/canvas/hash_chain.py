"""SHA-256 hash chain enforcement for Vellum sheets.

Every SheetEntry's hash = sha256(prev_hash || content). The chain
provides tamper-detection: if any entry is altered after the fact the
downstream hashes break. This module validates chains and computes
the next link.

Signed-by: Devon-8c5f | 2026-05-11 | AMP-324
"""

from __future__ import annotations

import hashlib

from vellum.models.entry import SheetEntry


SEPARATOR = "||"


class HashChain:
    """Stateless hash-chain utilities."""

    @staticmethod
    async def compute_next_hash(prev_hash: str, content: str) -> str:
        """Compute sha256(prev_hash || content) for the next entry."""
        payload = f"{prev_hash}{SEPARATOR}{content}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    async def verify_entry(entry: SheetEntry) -> bool:
        """Verify a single entry's hash is consistent with its fields."""
        expected = await HashChain.compute_next_hash(
            entry.prev_hash,
            entry.content,
        )
        return entry.entry_hash == expected

    @staticmethod
    async def validate_chain(entries: list[SheetEntry]) -> bool:
        """Validate the full hash chain across an ordered list of entries.

        Returns True when:
        - the list is empty (vacuously valid), or
        - the first entry has prev_hash == "" and each subsequent entry's
          prev_hash equals the preceding entry's entry_hash, and every
          entry's own hash is correct.
        """
        if not entries:
            return True

        for idx, entry in enumerate(entries):
            if not await HashChain.verify_entry(entry):
                return False

            if idx == 0:
                if entry.prev_hash != "":
                    return False
            else:
                if entry.prev_hash != entries[idx - 1].entry_hash:
                    return False

        return True
