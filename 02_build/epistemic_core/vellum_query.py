"""Vellum query surface — read events back, not just write them.

Provides filtered, sorted access to the Vellum event stream.
The store is write-permanent, but this module gives humans and agents
a way to ask: "what happened to this subject?", "show me all marketing
transitions today", "show me all deletion receipts".

Queries never mutate. Vellum is permanent.

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from epistemic_core.tiers import EpistemicTier
from epistemic_core.vellum_emitter import VellumStore
from epistemic_core.vellum_event import VellumEvent


# ---------------------------------------------------------------------------
# Query filters
# ---------------------------------------------------------------------------


class VellumQuery(BaseModel):
    """A filter specification for querying Vellum events.

    All fields are optional — unset fields match everything.
    Filters are ANDed together.
    """

    subject_id: str | None = None
    event_type: str | None = None
    event_type_prefix: str | None = None
    component: str | None = None
    actor: str | None = None
    epistemic_tier: EpistemicTier | None = None
    correlation_id: str | None = None
    workflow_id: str | None = None
    after: datetime | None = None
    before: datetime | None = None
    new_state: str | None = None
    metadata_contains: dict[str, Any] | None = None
    limit: int = 100


# ---------------------------------------------------------------------------
# Query result
# ---------------------------------------------------------------------------


class VellumQueryResult(BaseModel):
    """Result of a Vellum query."""

    events: list[VellumEvent] = Field(default_factory=list)
    total_matched: int = 0
    truncated: bool = False

    @property
    def empty(self) -> bool:
        return len(self.events) == 0


# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------


def _matches(event: VellumEvent, query: VellumQuery) -> bool:
    """Check if a single event matches all query filters."""
    if query.subject_id is not None and event.subject_id != query.subject_id:
        return False
    if query.event_type is not None and event.event_type != query.event_type:
        return False
    if query.event_type_prefix is not None and not event.event_type.startswith(
        query.event_type_prefix,
    ):
        return False
    if query.component is not None and event.component != query.component:
        return False
    if query.actor is not None and event.actor != query.actor:
        return False
    if query.epistemic_tier is not None and event.epistemic_tier != query.epistemic_tier:
        return False
    if query.correlation_id is not None and event.correlation_id != query.correlation_id:
        return False
    if query.workflow_id is not None and event.workflow_id != query.workflow_id:
        return False
    if query.after is not None and event.timestamp <= query.after:
        return False
    if query.before is not None and event.timestamp >= query.before:
        return False
    if query.new_state is not None and event.new_state != query.new_state:
        return False
    if query.metadata_contains is not None:
        for k, v in query.metadata_contains.items():
            if event.metadata.get(k) != v:
                return False
    return True


def query_events(store: VellumStore, query: VellumQuery) -> VellumQueryResult:
    """Query the Vellum store for events matching the filter.

    Returns events sorted by timestamp (newest first), limited to query.limit.
    """
    all_events = store.all_events()
    matched = [ev for ev in all_events if _matches(ev, query)]
    matched.sort(key=lambda ev: ev.timestamp, reverse=True)

    total = len(matched)
    truncated = total > query.limit
    events = matched[: query.limit]

    return VellumQueryResult(
        events=events,
        total_matched=total,
        truncated=truncated,
    )


# ---------------------------------------------------------------------------
# Convenience helpers — common query patterns
# ---------------------------------------------------------------------------


def events_for_subject(
    store: VellumStore,
    subject_id: str,
    *,
    limit: int = 100,
) -> VellumQueryResult:
    """All events for a given subject (e.g. an artifact_id, session_id)."""
    return query_events(store, VellumQuery(subject_id=subject_id, limit=limit))


def events_by_component(
    store: VellumStore,
    component: str,
    *,
    after: datetime | None = None,
    limit: int = 100,
) -> VellumQueryResult:
    """All events emitted by a specific component."""
    return query_events(
        store,
        VellumQuery(component=component, after=after, limit=limit),
    )


def events_by_type_prefix(
    store: VellumStore,
    prefix: str,
    *,
    after: datetime | None = None,
    limit: int = 100,
) -> VellumQueryResult:
    """All events matching a type prefix (e.g. 'marketing.' for all marketing events)."""
    return query_events(
        store,
        VellumQuery(event_type_prefix=prefix, after=after, limit=limit),
    )


def deletion_receipts(
    store: VellumStore,
    *,
    after: datetime | None = None,
    limit: int = 100,
) -> VellumQueryResult:
    """All deletion receipt events (from sidecar cleanup, etc.)."""
    return query_events(
        store,
        VellumQuery(event_type_prefix="sidecar.deletion_receipt", after=after, limit=limit),
    )


def state_transitions_for_subject(
    store: VellumStore,
    subject_id: str,
) -> list[tuple[str, str, datetime]]:
    """Return the sequence of state transitions for a subject.

    Returns list of (previous_state, new_state, timestamp) tuples,
    ordered chronologically (oldest first).
    """
    result = events_for_subject(store, subject_id, limit=10000)
    transitions = [
        (ev.previous_state, ev.new_state, ev.timestamp)
        for ev in result.events
        if ev.new_state
    ]
    transitions.sort(key=lambda t: t[2])
    return transitions
