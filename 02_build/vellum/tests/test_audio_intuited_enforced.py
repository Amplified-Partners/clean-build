"""§2.2 — Audio-INTUITED enforcement at the entry boundary.

Proves that entries derived from audio sources cannot claim a tier
above INTUITED. The min-rule says audio input is INTUITED — period.
Supplying STRUCTURED or higher on an audio-derived entry is a
silent promotion, which is a P0 violation.

Dana | 2026-05-20 | P0 test §2.2
"""

from __future__ import annotations

import pytest

from vellum.models.entry import AUDIO_DERIVED_SOURCES, SheetEntry


class TestAudioIntuitedEnforcement:
    """Audio-derived entries must be INTUITED. No exceptions."""

    def test_audio_source_intuited_accepted(self) -> None:
        """Happy path: audio entry with INTUITED tier is fine."""
        entry = SheetEntry(
            sheet_id="s1",
            author="ewan",
            content="transcribed speech",
            epistemic_tier="INTUITED",
            metadata={"source": "audio"},
        )
        assert entry.epistemic_tier == "INTUITED"

    def test_audio_source_structured_rejected(self) -> None:
        """Supplying STRUCTURED on an audio entry = silent promotion = rejected."""
        with pytest.raises(ValueError, match="Audio-derived entries must be INTUITED"):
            SheetEntry(
                sheet_id="s1",
                author="ewan",
                content="transcribed speech",
                epistemic_tier="STRUCTURED",
                metadata={"source": "audio"},
            )

    def test_audio_source_measured_rejected(self) -> None:
        with pytest.raises(ValueError, match="Audio-derived entries must be INTUITED"):
            SheetEntry(
                sheet_id="s1",
                author="ewan",
                content="transcribed speech",
                epistemic_tier="MEASURED",
                metadata={"source": "audio"},
            )

    def test_audio_source_proven_rejected(self) -> None:
        with pytest.raises(ValueError, match="Audio-derived entries must be INTUITED"):
            SheetEntry(
                sheet_id="s1",
                author="ewan",
                content="transcribed speech",
                epistemic_tier="PROVEN",
                metadata={"source": "audio"},
            )

    def test_transcribed_by_enforced(self) -> None:
        """transcribed_by metadata also triggers the audio-INTUITED rule."""
        with pytest.raises(ValueError, match="Audio-derived entries must be INTUITED"):
            SheetEntry(
                sheet_id="s1",
                author="ewan",
                content="transcribed by whisper",
                epistemic_tier="STRUCTURED",
                metadata={"transcribed_by": "whisper-large-v3"},
            )

    def test_transcribed_by_intuited_accepted(self) -> None:
        entry = SheetEntry(
            sheet_id="s1",
            author="ewan",
            content="transcribed by whisper",
            epistemic_tier="INTUITED",
            metadata={"transcribed_by": "whisper-large-v3"},
        )
        assert entry.epistemic_tier == "INTUITED"

    def test_all_audio_sources_enforced(self) -> None:
        """Every value in AUDIO_DERIVED_SOURCES triggers the rule."""
        for source in AUDIO_DERIVED_SOURCES:
            with pytest.raises(ValueError, match="Audio-derived"):
                SheetEntry(
                    sheet_id="s1",
                    author="ewan",
                    content=f"from {source}",
                    epistemic_tier="STRUCTURED",
                    metadata={"source": source},
                )

    def test_non_audio_structured_allowed(self) -> None:
        """Non-audio entries CAN claim STRUCTURED — the rule only applies to audio."""
        entry = SheetEntry(
            sheet_id="s1",
            author="agent-1",
            content="structured analysis output",
            epistemic_tier="STRUCTURED",
            metadata={"source": "analysis"},
        )
        assert entry.epistemic_tier == "STRUCTURED"

    def test_no_metadata_source_allowed(self) -> None:
        """No source metadata at all — no restriction, default INTUITED."""
        entry = SheetEntry(
            sheet_id="s1",
            author="ewan",
            content="just a comment",
        )
        assert entry.epistemic_tier == "INTUITED"

    def test_case_insensitive_source(self) -> None:
        """Source matching is case-insensitive."""
        with pytest.raises(ValueError, match="Audio-derived"):
            SheetEntry(
                sheet_id="s1",
                author="ewan",
                content="transcribed",
                epistemic_tier="STRUCTURED",
                metadata={"source": "AUDIO"},
            )
