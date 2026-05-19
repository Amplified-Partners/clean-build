"""
Audit log — the system's memory of its own honesty.

Append-only, thread-safe. In production this writes to PostgreSQL/Vellum.
For the reference implementation and tests: in-memory.

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import threading
from collections.abc import Callable

from epistemic_core.tiers import EpistemicTier
from epistemic_core.min_rule import Provenance, PreconditionCheck

log = logging.getLogger("amplified.epistemic.audit")


@dataclasses.dataclass(frozen=True)
class StatusRecord:
    """One audit-log entry. Written for every decision the system makes."""

    record_id: str
    timestamp: dt.datetime
    layer: str
    declared_status: EpistemicTier
    effective_status: EpistemicTier
    provenance: Provenance
    preconditions: tuple[PreconditionCheck, ...]
    sample_size: int | None = None
    note: str = ""


class AuditLog:
    """Append-only log. In production this writes to PostgreSQL/Vellum.

    For the reference implementation, in-memory and thread-safe.
    Supports subscriber hooks for downstream consumers (drift detector,
    Vellum emitter, etc.).
    """

    def __init__(self) -> None:
        self._records: list[StatusRecord] = []
        self._lock = threading.Lock()
        self._on_record: list[Callable[[StatusRecord], None]] = []

    def write(self, record: StatusRecord) -> None:
        """Append a record and notify all subscribers.

        Guarantees:
        1. The record is always appended before hooks run.
        2. ALL hooks are called, even if earlier hooks raise.
        3. If any hook raises, the first exception is re-raised
           after all hooks have been called.

        This ensures the audit trail is never lost — not even for
        the incident that caused the crash.
        """
        with self._lock:
            self._records.append(record)
        log.debug(
            "AUDIT: %s declared=%s effective=%s",
            record.layer,
            record.declared_status.label(),
            record.effective_status.label(),
        )
        first_exc: Exception | None = None
        for hook in self._on_record:
            try:
                hook(record)
            except Exception as exc:
                log.error("Subscriber hook %s raised: %s", hook, exc)
                if first_exc is None:
                    first_exc = exc
        if first_exc is not None:
            raise first_exc

    def subscribe(self, hook: Callable[[StatusRecord], None]) -> None:
        """Register a callback for every new record."""
        self._on_record.append(hook)

    def all(self) -> tuple[StatusRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def clear(self) -> None:
        """For testing only."""
        with self._lock:
            self._records.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._records)
