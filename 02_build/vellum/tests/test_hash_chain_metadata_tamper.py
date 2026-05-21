"""§2.1 — Hash chain metadata tamper detection.

Proves that v2 hash chain catches tampering of ANY field, not just content.
The old v1 chain only covered prev_hash||content — an attacker could mutate
entry_type, author, timestamp, or metadata without breaking the chain.
v2 closes this gap.

Also validates:
- v1 backward compat (legacy entries still verify under v1 rules)
- chain_version migration marker (v1 and v2 entries coexist in a chain)
- canonical JSON determinism (same inputs always produce same hash)

Dana | 2026-05-20 | P0 test §2.1
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest

from vellum.canvas.hash_chain import HashChain
from vellum.models.entry import CHAIN_VERSION, SheetEntry, _canonical_json


class TestV2HashCoversAllFields:
    """v2 hash protects every field — mutating any one breaks the chain."""

    def _make_entry(self, **overrides) -> SheetEntry:
        defaults = dict(
            sheet_id="s1",
            author="ewan",
            content="approved — go with option A",
            entry_type="decision",
            epistemic_tier="INTUITED",
            metadata={"source": "text"},
        )
        defaults.update(overrides)
        return SheetEntry(**defaults)

    def test_tamper_entry_type_detected(self) -> None:
        """The tier-laundering vector: mutating entry_type from agent_write
        to decision without breaking the chain. v2 catches this."""
        entry = self._make_entry()
        original_hash = entry.entry_hash
        assert HashChain.verify_entry(entry)

        # Tamper entry_type — this was the P0 vulnerability
        entry.entry_type = "agent_write"
        assert entry.entry_hash == original_hash  # hash field unchanged
        assert not HashChain.verify_entry(entry)  # but recomputation catches it

    def test_tamper_author_detected(self) -> None:
        entry = self._make_entry()
        assert HashChain.verify_entry(entry)
        entry.author = "attacker"
        assert not HashChain.verify_entry(entry)

    def test_tamper_metadata_detected(self) -> None:
        entry = self._make_entry(metadata={"source": "text", "key": "value"})
        assert HashChain.verify_entry(entry)
        entry.metadata["key"] = "tampered"
        assert not HashChain.verify_entry(entry)

    def test_tamper_epistemic_tier_detected(self) -> None:
        """Promoting INTUITED to STRUCTURED without evidence = tier laundering."""
        entry = self._make_entry(epistemic_tier="INTUITED")
        assert HashChain.verify_entry(entry)
        entry.epistemic_tier = "STRUCTURED"
        assert not HashChain.verify_entry(entry)

    def test_tamper_timestamp_detected(self) -> None:
        entry = self._make_entry()
        assert HashChain.verify_entry(entry)
        entry.timestamp = datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert not HashChain.verify_entry(entry)

    def test_tamper_content_still_detected(self) -> None:
        """Content tampering was always caught — confirm v2 didn't regress."""
        entry = self._make_entry()
        assert HashChain.verify_entry(entry)
        entry.content = "this was not what was said"
        assert not HashChain.verify_entry(entry)

    def test_tamper_sheet_id_detected(self) -> None:
        entry = self._make_entry()
        assert HashChain.verify_entry(entry)
        entry.sheet_id = "different-sheet"
        assert not HashChain.verify_entry(entry)


class TestV1BackwardCompat:
    """v1 entries still verify under v1 rules for migration support."""

    def test_v1_entry_verifies(self) -> None:
        entry = SheetEntry(
            sheet_id="s1",
            author="test",
            content="hello",
            chain_version=1,
        )
        assert entry.chain_version == 1
        assert HashChain.verify_entry(entry)

    def test_v1_metadata_tamper_not_detected(self) -> None:
        """v1 INTENTIONALLY does not protect metadata — this is the known gap."""
        entry = SheetEntry(
            sheet_id="s1",
            author="test",
            content="hello",
            chain_version=1,
        )
        entry.author = "attacker"
        # v1 hash only covers prev_hash||content, so author change is invisible
        assert HashChain.verify_entry(entry)

    def test_v1_content_tamper_still_detected(self) -> None:
        entry = SheetEntry(
            sheet_id="s1",
            author="test",
            content="hello",
            chain_version=1,
        )
        entry.content = "tampered"
        assert not HashChain.verify_entry(entry)


class TestMixedVersionChain:
    """v1 and v2 entries can coexist in a chain (migration path)."""

    def test_v1_then_v2_chain_validates(self) -> None:
        e1 = SheetEntry(
            sheet_id="s1",
            author="a",
            content="first (legacy)",
            prev_hash="",
            chain_version=1,
        )
        e2 = SheetEntry(
            sheet_id="s1",
            author="b",
            content="second (v2)",
            prev_hash=e1.entry_hash,
            chain_version=2,
        )
        assert HashChain.validate_chain([e1, e2])

    def test_default_version_is_v2(self) -> None:
        entry = SheetEntry(sheet_id="s1", author="test", content="hello")
        assert entry.chain_version == CHAIN_VERSION
        assert entry.chain_version == 2


class TestCanonicalJsonDeterminism:
    """Same inputs always produce the same hash — no ordering surprises."""

    def test_dict_key_order_irrelevant(self) -> None:
        a = {"z": 1, "a": 2, "m": 3}
        b = {"a": 2, "m": 3, "z": 1}
        assert _canonical_json(a) == _canonical_json(b)

    def test_identical_entries_same_hash(self) -> None:
        ts = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
        e1 = SheetEntry(
            sheet_id="s1", author="a", content="hello",
            timestamp=ts, entry_type="agent_write",
        )
        e2 = SheetEntry(
            sheet_id="s1", author="a", content="hello",
            timestamp=ts, entry_type="agent_write",
        )
        assert e1.entry_hash == e2.entry_hash

    def test_different_metadata_different_hash(self) -> None:
        ts = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
        e1 = SheetEntry(
            sheet_id="s1", author="a", content="hello",
            timestamp=ts, metadata={"x": 1},
        )
        e2 = SheetEntry(
            sheet_id="s1", author="a", content="hello",
            timestamp=ts, metadata={"x": 2},
        )
        assert e1.entry_hash != e2.entry_hash
