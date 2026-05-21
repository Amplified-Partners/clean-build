"""Sheet entry — the atomic unit of a Vellum sheet.

Every entry is hash-chained, attributed, timestamped, and immutable.

Chain version 2 (2026-05-20): hash covers all protected fields
(prev_hash, sheet_id, author, content, timestamp, entry_type,
epistemic_tier, metadata). Version 1 covered only prev_hash || content
and is retained for backward-compatible verification of legacy entries.

Audio-INTUITED rule enforced at the entry boundary: entries derived
from audio sources cannot claim a tier above INTUITED. This is the
min-rule applied at the storage boundary — belt and braces alongside
the gate.

Devon-b5dc | 2026-05-14
Hardened by Dana | 2026-05-20 | P0 §2.1 hash payload, §2.2 epistemic enforcement, §2.3 telemetry types
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Chain versioning
# ---------------------------------------------------------------------------

CHAIN_VERSION = 2


# ---------------------------------------------------------------------------
# Entry types — partitioned by mode (§2.3)
# ---------------------------------------------------------------------------

CONTACT_ENTRY_TYPES = frozenset({
    "agent_write", "human_comment", "emoji_reaction", "decision",
    "read_receipt", "task_created", "brief_summary", "cleaned_prompt",
    "council_question", "council_answer",
})

TELEMETRY_ENTRY_TYPES = frozenset({
    "telemetry", "health_check", "metric", "pattern_match",
})

EntryType = Literal[
    # Contact surface
    "agent_write",
    "human_comment",
    "emoji_reaction",
    "decision",
    "read_receipt",
    "task_created",
    "brief_summary",
    "cleaned_prompt",
    "council_question",
    "council_answer",
    # Telemetry
    "telemetry",
    "health_check",
    "metric",
    "pattern_match",
]

EpistemicTier = Literal["INTUITED", "STRUCTURED", "MEASURED", "PROVEN"]

# Sources that are always INTUITED — the audio-INTUITED rule (§2.2)
AUDIO_DERIVED_SOURCES = frozenset({"audio", "voice", "transcription", "whisper"})


# ---------------------------------------------------------------------------
# Canonical JSON — deterministic serialisation for hashing
# ---------------------------------------------------------------------------


def _canonical_json(obj: dict) -> bytes:
    """Deterministic JSON for hashing. Sorted keys, no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


# ---------------------------------------------------------------------------
# SheetEntry
# ---------------------------------------------------------------------------


class SheetEntry(BaseModel):
    """A single line on a Vellum sheet. Immutable once written.

    Chain version 2: hash = sha256(canonical_json(all protected fields)).
    Chain version 1: hash = sha256(prev_hash || content).
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    sheet_id: str
    author: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    prev_hash: str = ""
    entry_hash: str = ""
    entry_type: EntryType = "agent_write"
    epistemic_tier: EpistemicTier = "INTUITED"
    metadata: dict = Field(default_factory=dict)
    chain_version: int = CHAIN_VERSION

    def compute_hash(self) -> str:
        """Compute the entry hash. Version-aware.

        v1: sha256(prev_hash || content) — metadata unprotected (legacy).
        v2: sha256(canonical_json(all protected fields)) — full coverage.
        """
        if self.chain_version == 1:
            payload = f"{self.prev_hash}||{self.content}".encode("utf-8")
            return hashlib.sha256(payload).hexdigest()
        # v2: canonical JSON over all protected fields
        payload_obj = {
            "prev_hash": self.prev_hash,
            "sheet_id": self.sheet_id,
            "author": self.author,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "entry_type": self.entry_type,
            "epistemic_tier": self.epistemic_tier,
            "metadata": self.metadata,
        }
        return hashlib.sha256(_canonical_json(payload_obj)).hexdigest()

    def model_post_init(self, __context: object) -> None:
        if not self.entry_hash:
            self.entry_hash = self.compute_hash()

    @model_validator(mode="after")
    def _enforce_audio_intuited(self) -> SheetEntry:
        """Audio-INTUITED rule: entries from audio sources cannot claim
        higher than INTUITED. This is the min-rule at the entry boundary.
        """
        source = str(self.metadata.get("source", "")).lower()
        transcribed_by = self.metadata.get("transcribed_by", "")
        if source in AUDIO_DERIVED_SOURCES or transcribed_by:
            if self.epistemic_tier != "INTUITED":
                raise ValueError(
                    f"Audio-derived entries must be INTUITED, got {self.epistemic_tier!r}. "
                    f"Source: {source or transcribed_by}. "
                    "The min-rule forbids promoting audio input."
                )
        return self
