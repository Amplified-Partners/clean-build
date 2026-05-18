"""Vellum Drift Detector — watches every record for the lying condition.

Follows the exact pattern from epistemic_status.py v2 reference implementation.
Subscribes to the ingestion gate. Fires signal on every record that passes through.

Signals:
  GREEN  — all declared statuses match observed behaviour
  AMBER  — a record has been demoted (effective < claimed, gap == 1)
  RED    — operating below declared status by 1 tier, accumulating
  BLACK  — status laundering detected. Gap >= 2 tiers. P0. System halts.

Devon-b5dc | 2026-05-14
"""

from __future__ import annotations

import datetime as dt
import enum
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from vellum.gate.models import EpistemicStatus
from vellum.ingestion.models import GateVerdict, SignedRecord

log = logging.getLogger("vellum.drift")


# ---------------------------------------------------------------------------
# Signal enum — matches epistemic_status.py v2
# ---------------------------------------------------------------------------


class DriftSignal(enum.Enum):
    """The four drift states. Order matters for severity."""

    GREEN = "GREEN"    # All declared statuses match observed behaviour
    AMBER = "AMBER"    # A precondition is within tolerance but stressed
    RED = "RED"        # Operating below declared status by 1 tier (P1)
    BLACK = "BLACK"    # Status laundering detected — gap >= 2 tiers (P0)


# ---------------------------------------------------------------------------
# P0 Incident — the lying condition
# ---------------------------------------------------------------------------


class P0Incident(Exception):
    """Raised when Vellum catches status laundering.

    The system MUST halt. A deterministic fallback may be returned to the
    caller, but the apparatus does not continue making decisions until a
    human has signed off.
    """


# ---------------------------------------------------------------------------
# Drift event record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DriftEvent:
    """One drift observation. Immutable."""

    timestamp: dt.datetime
    signal: DriftSignal
    submission_id: str
    declared_tier: EpistemicStatus
    effective_tier: EpistemicStatus
    gap: int
    reason: str


# ---------------------------------------------------------------------------
# The Drift Detector
# ---------------------------------------------------------------------------


class VellumDriftDetector:
    """Watches every verdict from the ingestion gate. Fires signals.

    Pattern matches epistemic_status.py v2 DriftDetector:
    - Subscribes via hook
    - Fires GREEN/AMBER/RED/BLACK
    - BLACK raises P0Incident (system halt)
    - Thread-safe (lock around state mutation)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._signal: DriftSignal = DriftSignal.GREEN
        self._events: list[DriftEvent] = []
        self._on_signal: list[Callable[[DriftEvent], None]] = []
        self._red_count: int = 0  # Accumulates RED signals

    @property
    def signal(self) -> DriftSignal:
        """Current drift signal."""
        with self._lock:
            return self._signal

    @property
    def events(self) -> list[DriftEvent]:
        """All drift events (read-only copy)."""
        with self._lock:
            return list(self._events)

    @property
    def red_count(self) -> int:
        """Number of accumulated RED signals."""
        with self._lock:
            return self._red_count

    def subscribe(self, hook: Callable[[DriftEvent], None]) -> None:
        """Register a hook called on every drift event."""
        self._on_signal.append(hook)

    def observe_verdict(
        self,
        verdict: GateVerdict,
        claimed_tier: EpistemicStatus,
    ) -> DriftEvent:
        """Observe a gate verdict and compute drift signal.

        Called after every gate evaluation (accepted OR rejected).
        The drift detector watches everything — not just acceptances.

        Args:
            verdict: The gate's verdict (ACCEPTED or REJECTED)
            claimed_tier: What the submitter claimed

        Returns:
            The DriftEvent produced

        Raises:
            P0Incident: If BLACK signal fires (gap >= 2, laundering detected)
        """
        now = dt.datetime.now(dt.timezone.utc)
        effective = verdict.effective_tier
        gap = claimed_tier.value - effective.value

        # Determine signal
        if verdict.decision == "REJECTED":
            # Rejected submissions with tier violations are AMBER
            # (someone tried, the gate caught it — that's the system working)
            if any("TIER_EXCEEDS_CEILING" in rc for rc in verdict.reason_codes):
                signal = DriftSignal.AMBER
                reason = (
                    f"Submission {verdict.submission_id} claimed "
                    f"{claimed_tier.label()} but ceiling enforced. "
                    "Gate caught it. System working correctly."
                )
            else:
                # Other rejections don't affect drift signal
                signal = self._signal  # Maintain current state
                reason = f"Submission {verdict.submission_id} rejected: {verdict.reason_codes}"

        elif gap >= 2:
            # BLACK: laundering condition. Gap >= 2 between claimed and effective.
            # This should not happen if the gate is working — but if it does, P0.
            signal = DriftSignal.BLACK
            reason = (
                f"P0 LAUNDERING: submission {verdict.submission_id} "
                f"declared {claimed_tier.label()}, effective "
                f"{effective.label()}. Gap={gap} tiers. "
                "Status laundering detected. System must halt."
            )

        elif gap == 1:
            # RED: honest demotion by 1 tier. Not laundering, but operating
            # below declared status.
            signal = DriftSignal.RED
            reason = (
                f"Demotion: submission {verdict.submission_id} "
                f"declared {claimed_tier.label()}, effective "
                f"{effective.label()}. Gap=1 tier. Honest demotion."
            )

        else:
            # GREEN: declared matches effective (or effective is higher, which
            # can't happen with min-rule but defensive coding).
            signal = DriftSignal.GREEN
            reason = (
                f"Submission {verdict.submission_id} accepted at "
                f"{effective.label()}. No drift."
            )

        event = DriftEvent(
            timestamp=now,
            signal=signal,
            submission_id=verdict.submission_id,
            declared_tier=claimed_tier,
            effective_tier=effective,
            gap=max(0, gap),
            reason=reason,
        )

        with self._lock:
            self._events.append(event)
            self._signal = signal

            if signal == DriftSignal.RED:
                self._red_count += 1
            elif signal == DriftSignal.GREEN:
                self._red_count = 0  # Reset on green

            # Hooks inside lock (v2 pattern: atomic end-to-end)
            for hook in self._on_signal:
                hook(event)

        # BLACK fires P0 AFTER recording the event
        if signal == DriftSignal.BLACK:
            log.critical(reason)
            raise P0Incident(reason)

        if signal == DriftSignal.RED:
            log.error(reason)
        elif signal == DriftSignal.AMBER:
            log.warning(reason)

        return event
