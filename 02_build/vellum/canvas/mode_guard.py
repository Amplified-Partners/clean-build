"""Mode/entry-type isolation — §2.3.

Each SheetMode defines which EntryType values are permitted.
Telemetry entries stay out of contact-surface sheets. Contact-surface
entries stay out of telemetry sheets. Enforced at the storage boundary.

Dana | 2026-05-20 | P0 §2.3
"""

from __future__ import annotations


class ModeViolationError(ValueError):
    """Raised when an entry type is not permitted for the sheet's mode."""

    def __init__(self, mode: str, entry_type: str) -> None:
        self.mode = mode
        self.entry_type = entry_type
        super().__init__(
            f"Entry type {entry_type!r} is not permitted on a {mode!r} sheet. "
            f"Allowed types: {sorted(MODE_ALLOWED_TYPES.get(mode, set()))}"
        )


# Mode → allowed entry types. read_receipt included in all contact-surface
# modes (infrastructure, not content).
MODE_ALLOWED_TYPES: dict[str, frozenset[str]] = {
    "brief": frozenset({
        "agent_write", "human_comment", "emoji_reaction", "decision",
        "read_receipt", "task_created", "brief_summary", "cleaned_prompt",
    }),
    "council": frozenset({
        "agent_write", "human_comment", "council_question",
        "council_answer", "decision", "read_receipt",
    }),
    "correspondence": frozenset({
        "agent_write", "human_comment", "cleaned_prompt",
        "decision", "read_receipt",
    }),
    "telemetry": frozenset({
        "telemetry", "health_check", "metric", "pattern_match",
    }),
}


def validate_mode_entry_type(mode: str, entry_type: str) -> None:
    """Raise ModeViolationError if entry_type is not allowed for mode."""
    allowed = MODE_ALLOWED_TYPES.get(mode)
    if allowed is None:
        raise ModeViolationError(mode, entry_type)
    if entry_type not in allowed:
        raise ModeViolationError(mode, entry_type)
