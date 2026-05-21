"""SHA-256 hash chain enforcement for Vellum sheets.

Version-aware verification:
  v2 (2026-05-20): hash = sha256(canonical_json(all protected fields))
  v1 (legacy): hash = sha256(prev_hash || content)

The chain provides tamper-detection: alter any field of any entry
and downstream hashes break. v2 extends protection to metadata,
author, entry_type, epistemic_tier — closing the tier-laundering
vector identified in the Perplexity review §2.1.

Devon-b5dc | 2026-05-14
Hardened by Dana | 2026-05-20 | §2.1 version-aware verification
"""

from __future__ import annotations

import hashlib

from vellum.models.entry import SheetEntry

SEPARATOR = "||"


class HashChain:

    @staticmethod
    def compute_next_hash(prev_hash: str, content: str) -> str:
        """Legacy v1 hash computation. Retained for backward compat.

        New code should use SheetEntry.compute_hash() which is version-aware.
        """
        payload = f"{prev_hash}{SEPARATOR}{content}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def verify_entry(entry: SheetEntry) -> bool:
        """Verify an entry's hash. Version-aware — delegates to entry."""
        return entry.entry_hash == entry.compute_hash()

    @staticmethod
    def validate_chain(entries: list[SheetEntry]) -> bool:
        if not entries:
            return True
        for idx, entry in enumerate(entries):
            if not HashChain.verify_entry(entry):
                return False
            if idx == 0:
                if entry.prev_hash != "":
                    return False
            else:
                if entry.prev_hash != entries[idx - 1].entry_hash:
                    return False
        return True
