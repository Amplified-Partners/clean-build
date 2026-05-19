"""Tests for Vellum query surface — read events back, not just write them.

Covers:
  1. Basic query by subject_id
  2. Query by event_type and event_type_prefix
  3. Query by component and actor
  4. Time-range filters (after, before)
  5. State transition history for a subject
  6. Convenience helpers (events_for_subject, events_by_component, etc.)
  7. Metadata contains filter
  8. Limit and truncation
  9. Empty results
 10. Deletion receipts helper

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from epistemic_core.tiers import EpistemicTier  # noqa: E402
from epistemic_core.vellum_emitter import MemoryVellumStore  # noqa: E402
from epistemic_core.vellum_event import VellumEvent  # noqa: E402
from epistemic_core.vellum_query import (  # noqa: E402
    VellumQuery,
    deletion_receipts,
    events_by_component,
    events_by_type_prefix,
    events_for_subject,
    query_events,
    state_transitions_for_subject,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store_with_events() -> MemoryVellumStore:
    """Build a store with a known set of events for testing."""
    store = MemoryVellumStore()
    now = datetime.now(timezone.utc)

    events = [
        VellumEvent(
            event_type="marketing.draft_created",
            actor="marketing_consumer",
            component="marketing_consumer",
            subject_id="art-1",
            new_state="draft",
            timestamp=now - timedelta(hours=5),
            metadata={"channel": "email"},
        ),
        VellumEvent(
            event_type="marketing.reviewed",
            actor="marketing_consumer",
            component="marketing_consumer",
            subject_id="art-1",
            previous_state="draft",
            new_state="reviewed",
            timestamp=now - timedelta(hours=4),
            metadata={"channel": "email"},
        ),
        VellumEvent(
            event_type="marketing.approved",
            actor="marketing_consumer",
            component="marketing_consumer",
            subject_id="art-1",
            previous_state="reviewed",
            new_state="approved",
            timestamp=now - timedelta(hours=3),
            metadata={"channel": "email"},
        ),
        VellumEvent(
            event_type="marketing.sent",
            actor="marketing_consumer",
            component="marketing_consumer",
            subject_id="art-1",
            previous_state="approved",
            new_state="sent",
            timestamp=now - timedelta(hours=2),
            metadata={"channel": "email"},
        ),
        VellumEvent(
            event_type="sidecar.session_opened",
            actor="sidecar",
            component="sidecar",
            subject_id="sess-1",
            new_state="open",
            timestamp=now - timedelta(hours=1),
            epistemic_tier=EpistemicTier.INTUITED,
        ),
        VellumEvent(
            event_type="sidecar.deletion_receipt",
            actor="sidecar",
            component="sidecar",
            subject_id="sess-1",
            previous_state="closing",
            new_state="closed",
            timestamp=now - timedelta(minutes=30),
        ),
        VellumEvent(
            event_type="research.job_created",
            actor="research_pipe",
            component="research_pipe",
            subject_id="job-1",
            new_state="intake_open",
            timestamp=now - timedelta(minutes=10),
            metadata={"domain": "marketing_engine"},
        ),
    ]

    for ev in events:
        store.write_event(ev)

    return store


# ===================================================================
# 1. Basic query by subject_id
# ===================================================================


class TestQueryBySubject:
    def test_finds_all_events_for_subject(self) -> None:
        store = _store_with_events()
        result = events_for_subject(store, "art-1")
        assert result.total_matched == 4
        assert all(ev.subject_id == "art-1" for ev in result.events)

    def test_returns_empty_for_unknown_subject(self) -> None:
        store = _store_with_events()
        result = events_for_subject(store, "unknown-id")
        assert result.empty is True
        assert result.total_matched == 0


# ===================================================================
# 2. Query by event_type and prefix
# ===================================================================


class TestQueryByType:
    def test_exact_event_type(self) -> None:
        store = _store_with_events()
        result = query_events(store, VellumQuery(event_type="marketing.sent"))
        assert result.total_matched == 1
        assert result.events[0].new_state == "sent"

    def test_event_type_prefix(self) -> None:
        store = _store_with_events()
        result = events_by_type_prefix(store, "marketing.")
        assert result.total_matched == 4

    def test_sidecar_prefix(self) -> None:
        store = _store_with_events()
        result = events_by_type_prefix(store, "sidecar.")
        assert result.total_matched == 2


# ===================================================================
# 3. Query by component and actor
# ===================================================================


class TestQueryByComponentActor:
    def test_by_component(self) -> None:
        store = _store_with_events()
        result = events_by_component(store, "sidecar")
        assert result.total_matched == 2

    def test_by_actor(self) -> None:
        store = _store_with_events()
        result = query_events(store, VellumQuery(actor="research_pipe"))
        assert result.total_matched == 1
        assert result.events[0].subject_id == "job-1"


# ===================================================================
# 4. Time-range filters
# ===================================================================


class TestTimeRange:
    def test_after_filter(self) -> None:
        store = _store_with_events()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=2, minutes=30)
        result = query_events(store, VellumQuery(after=cutoff))
        # Should get events from last 2.5 hours: sent, session_opened, deletion_receipt, job_created
        assert result.total_matched >= 3

    def test_before_filter(self) -> None:
        store = _store_with_events()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=3, minutes=30)
        result = query_events(store, VellumQuery(before=cutoff))
        # Should get events older than 3.5 hours: draft_created, reviewed
        assert result.total_matched >= 1

    def test_time_window(self) -> None:
        store = _store_with_events()
        now = datetime.now(timezone.utc)
        result = query_events(
            store,
            VellumQuery(
                after=now - timedelta(hours=4, minutes=30),
                before=now - timedelta(hours=2, minutes=30),
            ),
        )
        # Events between 4.5 and 2.5 hours ago: reviewed, approved
        assert result.total_matched >= 1


# ===================================================================
# 5. State transitions
# ===================================================================


class TestStateTransitions:
    def test_marketing_transitions(self) -> None:
        store = _store_with_events()
        transitions = state_transitions_for_subject(store, "art-1")
        assert len(transitions) == 4
        states = [t[1] for t in transitions]
        assert states == ["draft", "reviewed", "approved", "sent"]

    def test_sidecar_transitions(self) -> None:
        store = _store_with_events()
        transitions = state_transitions_for_subject(store, "sess-1")
        assert len(transitions) == 2
        states = [t[1] for t in transitions]
        assert states == ["open", "closed"]

    def test_chronological_order(self) -> None:
        store = _store_with_events()
        transitions = state_transitions_for_subject(store, "art-1")
        timestamps = [t[2] for t in transitions]
        assert timestamps == sorted(timestamps)


# ===================================================================
# 6. Metadata contains
# ===================================================================


class TestMetadataFilter:
    def test_matches_channel(self) -> None:
        store = _store_with_events()
        result = query_events(
            store,
            VellumQuery(metadata_contains={"channel": "email"}),
        )
        assert result.total_matched == 4

    def test_matches_domain(self) -> None:
        store = _store_with_events()
        result = query_events(
            store,
            VellumQuery(metadata_contains={"domain": "marketing_engine"}),
        )
        assert result.total_matched == 1

    def test_no_match(self) -> None:
        store = _store_with_events()
        result = query_events(
            store,
            VellumQuery(metadata_contains={"channel": "twitter"}),
        )
        assert result.empty is True


# ===================================================================
# 7. Limit and truncation
# ===================================================================


class TestLimitTruncation:
    def test_limit_applied(self) -> None:
        store = _store_with_events()
        result = query_events(store, VellumQuery(limit=2))
        assert len(result.events) == 2
        assert result.total_matched == 7
        assert result.truncated is True

    def test_no_truncation(self) -> None:
        store = _store_with_events()
        result = query_events(store, VellumQuery(limit=100))
        assert result.truncated is False


# ===================================================================
# 8. Deletion receipts helper
# ===================================================================


class TestDeletionReceipts:
    def test_finds_deletion_receipts(self) -> None:
        store = _store_with_events()
        result = deletion_receipts(store)
        assert result.total_matched == 1
        assert result.events[0].event_type == "sidecar.deletion_receipt"


# ===================================================================
# 9. Combined filters (AND)
# ===================================================================


class TestCombinedFilters:
    def test_component_and_new_state(self) -> None:
        store = _store_with_events()
        result = query_events(
            store,
            VellumQuery(component="marketing_consumer", new_state="sent"),
        )
        assert result.total_matched == 1

    def test_actor_and_subject(self) -> None:
        store = _store_with_events()
        result = query_events(
            store,
            VellumQuery(actor="sidecar", subject_id="sess-1"),
        )
        assert result.total_matched == 2

    def test_epistemic_tier_filter(self) -> None:
        store = _store_with_events()
        result = query_events(
            store,
            VellumQuery(epistemic_tier=EpistemicTier.INTUITED),
        )
        assert result.total_matched >= 1


# ===================================================================
# 10. Newest first ordering
# ===================================================================


class TestOrdering:
    def test_newest_first(self) -> None:
        store = _store_with_events()
        result = query_events(store, VellumQuery())
        timestamps = [ev.timestamp for ev in result.events]
        assert timestamps == sorted(timestamps, reverse=True)
