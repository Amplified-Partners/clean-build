"""§2.3 — Mode/entry-type isolation.

Proves that telemetry entries cannot land on contact-surface sheets
and vice versa. Each SheetMode defines which EntryType values are
permitted — mismatches are rejected at the storage boundary.

Dana | 2026-05-20 | P0 test §2.3
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from vellum.canvas.mode_guard import MODE_ALLOWED_TYPES, ModeViolationError, validate_mode_entry_type
from vellum.models.entry import SheetEntry
from vellum.models.sheet import SheetMeta
from vellum.storage import init_store
from vellum.storage.memory import MemorySheetStore


@pytest_asyncio.fixture
async def store():
    s = await init_store()
    yield s
    if isinstance(s, MemorySheetStore):
        s.clear()


class TestModeGuardUnit:
    """Unit tests for the mode guard function."""

    def test_brief_allows_agent_write(self) -> None:
        validate_mode_entry_type("brief", "agent_write")  # should not raise

    def test_brief_rejects_telemetry(self) -> None:
        with pytest.raises(ModeViolationError):
            validate_mode_entry_type("brief", "telemetry")

    def test_brief_rejects_health_check(self) -> None:
        with pytest.raises(ModeViolationError):
            validate_mode_entry_type("brief", "health_check")

    def test_telemetry_allows_metric(self) -> None:
        validate_mode_entry_type("telemetry", "metric")

    def test_telemetry_rejects_human_comment(self) -> None:
        with pytest.raises(ModeViolationError):
            validate_mode_entry_type("telemetry", "human_comment")

    def test_telemetry_rejects_decision(self) -> None:
        with pytest.raises(ModeViolationError):
            validate_mode_entry_type("telemetry", "decision")

    def test_council_allows_council_question(self) -> None:
        validate_mode_entry_type("council", "council_question")

    def test_council_rejects_brief_summary(self) -> None:
        with pytest.raises(ModeViolationError):
            validate_mode_entry_type("council", "brief_summary")

    def test_council_rejects_telemetry(self) -> None:
        with pytest.raises(ModeViolationError):
            validate_mode_entry_type("council", "telemetry")

    def test_correspondence_allows_cleaned_prompt(self) -> None:
        validate_mode_entry_type("correspondence", "cleaned_prompt")

    def test_correspondence_rejects_council_question(self) -> None:
        with pytest.raises(ModeViolationError):
            validate_mode_entry_type("correspondence", "council_question")

    def test_unknown_mode_rejected(self) -> None:
        with pytest.raises(ModeViolationError):
            validate_mode_entry_type("nonexistent", "agent_write")


class TestModeGuardIntegration:
    """Integration tests: mode enforcement at the storage boundary."""

    @pytest.mark.asyncio
    async def test_telemetry_on_brief_sheet_rejected(self, store) -> None:
        """The canonical test case: a telemetry entry on a brief sheet."""
        meta = SheetMeta(title="Daily Brief", tenant_id="ewan", mode="brief")
        await store.create_sheet(meta)

        telemetry_entry = SheetEntry(
            sheet_id=meta.id,
            author="system",
            content="cpu_usage=42%",
            entry_type="telemetry",
        )
        with pytest.raises(ModeViolationError):
            await store.append_entry(meta.id, telemetry_entry)

    @pytest.mark.asyncio
    async def test_human_comment_on_telemetry_sheet_rejected(self, store) -> None:
        meta = SheetMeta(title="System Telemetry", tenant_id="ewan", mode="telemetry")
        await store.create_sheet(meta)

        comment = SheetEntry(
            sheet_id=meta.id,
            author="ewan",
            content="this looks wrong",
            entry_type="human_comment",
        )
        with pytest.raises(ModeViolationError):
            await store.append_entry(meta.id, comment)

    @pytest.mark.asyncio
    async def test_valid_entry_on_brief_accepted(self, store) -> None:
        meta = SheetMeta(title="Daily Brief", tenant_id="ewan", mode="brief")
        await store.create_sheet(meta)

        entry = SheetEntry(
            sheet_id=meta.id,
            author="agent-1",
            content="morning brief",
            entry_type="agent_write",
        )
        await store.append_entry(meta.id, entry)
        sheet = await store.get_sheet(meta.id)
        assert len(sheet.entries) == 1

    @pytest.mark.asyncio
    async def test_valid_telemetry_on_telemetry_accepted(self, store) -> None:
        meta = SheetMeta(title="System Telemetry", tenant_id="ewan", mode="telemetry")
        await store.create_sheet(meta)

        entry = SheetEntry(
            sheet_id=meta.id,
            author="system",
            content="health_check passed",
            entry_type="health_check",
        )
        await store.append_entry(meta.id, entry)
        sheet = await store.get_sheet(meta.id)
        assert len(sheet.entries) == 1

    @pytest.mark.asyncio
    async def test_council_question_on_brief_rejected(self, store) -> None:
        meta = SheetMeta(title="Daily Brief", tenant_id="ewan", mode="brief")
        await store.create_sheet(meta)

        entry = SheetEntry(
            sheet_id=meta.id,
            author="ewan",
            content="Should we deploy today?",
            entry_type="council_question",
        )
        with pytest.raises(ModeViolationError):
            await store.append_entry(meta.id, entry)


class TestAllModesHaveAllowedTypes:
    """Structural test: every mode has a non-empty set of allowed types."""

    def test_all_modes_defined(self) -> None:
        expected_modes = {"brief", "council", "correspondence", "telemetry"}
        assert set(MODE_ALLOWED_TYPES.keys()) == expected_modes

    def test_no_empty_allowed_sets(self) -> None:
        for mode, allowed in MODE_ALLOWED_TYPES.items():
            assert len(allowed) > 0, f"Mode {mode!r} has no allowed types"

    def test_no_overlap_between_telemetry_and_contact(self) -> None:
        """Telemetry types and contact-surface types must not overlap."""
        telemetry_types = MODE_ALLOWED_TYPES["telemetry"]
        for mode in ("brief", "council", "correspondence"):
            overlap = telemetry_types & MODE_ALLOWED_TYPES[mode]
            assert not overlap, f"Telemetry types overlap with {mode}: {overlap}"
