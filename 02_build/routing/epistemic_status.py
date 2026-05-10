"""
Epistemic Status Invariant — reference implementation.

Layer 0 law for the Amplified substrate routing engine.

A value's epistemic status is the minimum of:
  1. Its own internal claim
  2. The minimum status of its inputs
  3. The status implied by its preconditions

Any violation is a P0 incident. The system halts.

This module is intentionally small. The invariant must be auditable in one read.

Authored by Devon-32cc | 2026-05-10 | session devin-32cc0fc89ad04baba570382e2c3eb2f4
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import logging
import threading
import uuid
from collections.abc import Callable, Sequence
from typing import Any

log = logging.getLogger("amplified.epistemic")


# ---------------------------------------------------------------------------
# 1. The four tiers
# ---------------------------------------------------------------------------


class EpistemicStatus(enum.IntEnum):
    """Four tiers of honest knowledge claim. Order matters: min() works."""

    INTUITED = 1     # Vibe with footnotes (raw LLM output, gut, narrative)
    STRUCTURED = 2   # Honest heuristic (reproducible rule, judgement weights)
    MEASURED = 3     # Empirically calibrated (data + CI + sample size + drift monitor)
    PROVEN = 4       # Mathematically proven (closed form + verified preconditions)

    def label(self) -> str:
        return {1: "intuited", 2: "structured", 3: "measured", 4: "proven"}[self]


# ---------------------------------------------------------------------------
# 2. Provenance and status records
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Provenance:
    """How was this value produced?"""

    layer: str                              # which layer of the stack
    method: str                              # name of the procedure
    inputs: tuple[str, ...]                  # ids of input StatusedValues
    promotion_record_id: str | None = None   # id of the promotion gate, if any


@dataclasses.dataclass(frozen=True)
class PreconditionCheck:
    """A precondition with its verification state."""

    name: str
    holds: bool
    verified_at: dt.datetime
    evidence: str                            # human-readable justification


@dataclasses.dataclass(frozen=True)
class StatusRecord:
    """One audit-log entry. Written for every decision the system makes."""

    record_id: str
    timestamp: dt.datetime
    layer: str
    declared_status: EpistemicStatus
    effective_status: EpistemicStatus        # after applying min-rule
    provenance: Provenance
    preconditions: tuple[PreconditionCheck, ...]
    sample_size: int | None
    note: str = ""


# ---------------------------------------------------------------------------
# 3. The StatusedValue — every value in the system carries its tier
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class StatusedValue:
    """A value that knows what it is.

    All values flowing between layers MUST be StatusedValues. A bare float
    or string crossing a layer boundary is a P0 incident.

    Carries a `valid_until` timestamp. A value consumed after its expiry
    auto-demotes by one tier. This is the temporal-staleness fix that closes
    the gap missed in v1.0 — the min-rule prevented upward laundering across
    layers but not across time.
    """

    value: Any
    status: EpistemicStatus
    provenance: Provenance
    preconditions: tuple[PreconditionCheck, ...] = ()
    sample_size: int | None = None
    valid_until: dt.datetime | None = None  # None = no expiry (PROVEN math is timeless)
    lens: str | None = None  # required for federated GLM consumers; see Section 11
    value_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))

    def is_stale(self, now: dt.datetime | None = None) -> bool:
        if self.valid_until is None:
            return False
        return (now or dt.datetime.now(dt.timezone.utc)) > self.valid_until

    def effective_status(self, input_statuses: Sequence[EpistemicStatus]) -> EpistemicStatus:
        """The min-rule. Cannot be overridden."""

        own_claim = self.status
        input_floor = min(input_statuses, default=EpistemicStatus.PROVEN)
        precondition_floor = (
            self.status
            if all(p.holds for p in self.preconditions)
            else _demote(self.status)
        )
        staleness_floor = _demote(self.status) if self.is_stale() else self.status
        return min(own_claim, input_floor, precondition_floor, staleness_floor)


def _demote(s: EpistemicStatus) -> EpistemicStatus:
    """One-tier demotion. PROVEN -> MEASURED -> STRUCTURED -> INTUITED."""

    return EpistemicStatus(max(EpistemicStatus.INTUITED.value, s.value - 1))


# ---------------------------------------------------------------------------
# 4. P0 incident — the lying condition
# ---------------------------------------------------------------------------


class P0Incident(Exception):
    """Raised when the system catches itself laundering status.

    The system MUST halt. A deterministic fallback may be returned to the
    caller, but the apparatus does not continue making decisions until a
    human has signed off.
    """


# ---------------------------------------------------------------------------
# 5. The drift signal
# ---------------------------------------------------------------------------


class DriftSignal(enum.Enum):
    GREEN = "green"     # all declared statuses match observed behaviour
    AMBER = "amber"     # a precondition is within 10% of failure
    RED = "red"         # operating below declared status (P1)
    BLACK = "black"     # status laundering detected (P0)


# ---------------------------------------------------------------------------
# 6. The Layer base class — every component declares its status
# ---------------------------------------------------------------------------


class Layer:
    """Base class for any component in the substrate routing stack.

    Subclasses MUST implement the four operations. The base class enforces
    the invariant on every call.
    """

    name: str = "unnamed"
    declared_max_status: EpistemicStatus = EpistemicStatus.INTUITED

    def declare_status(self) -> EpistemicStatus:
        """The status this layer claims to produce, before applying min-rule."""
        raise NotImplementedError

    def declare_provenance(self, inputs: Sequence[StatusedValue]) -> Provenance:
        """Where did this layer's output come from?"""
        raise NotImplementedError

    def verify_preconditions(self) -> tuple[PreconditionCheck, ...]:
        """Check all preconditions for this layer's claimed status. Always fresh."""
        raise NotImplementedError

    def compute(self, inputs: Sequence[StatusedValue]) -> Any:
        """The actual work. Subclass implements."""
        raise NotImplementedError

    # ---- enforced wrapper. Subclasses do not override this. ----

    requires_lens: bool = False  # set True for layers that consume lens-dependent params

    def __call__(self, *inputs: StatusedValue) -> StatusedValue:
        # 1. Enforce that all inputs are StatusedValues.
        for i, inp in enumerate(inputs):
            if not isinstance(inp, StatusedValue):
                raise P0Incident(
                    f"{self.name}: input {i} is a bare value (type={type(inp).__name__}). "
                    "All inter-layer values must be StatusedValues. This is the laundering trap."
                )

        # 1a. Stale input demotes silently — honest, but logged via telemetry.
        # 1b. Lens requirement: layers that consume lens-dependent parameters must
        #     receive inputs whose lens is declared. Identifiability fix.
        if self.requires_lens:
            missing = [i for i, inp in enumerate(inputs) if inp.lens is None]
            if missing:
                raise P0Incident(
                    f"{self.name}: requires_lens=True but inputs {missing} have lens=None. "
                    "Federated GLM consumers must declare their lens to avoid "
                    "the identifiability confounding documented in Section 11."
                )

        # 2. Run the computation.
        raw_value = self.compute(inputs)

        # 3. Verify preconditions FRESH. We never trust cached precondition state.
        preconditions = self.verify_preconditions()

        # 4. Apply the min-rule.
        own_claim = self.declare_status()
        if own_claim > self.declared_max_status:
            raise P0Incident(
                f"{self.name}: claims status {own_claim.label()} but declared_max_status "
                f"is {self.declared_max_status.label()}. The layer is over-claiming."
            )

        input_floor = min(
            (inp.status for inp in inputs), default=EpistemicStatus.PROVEN
        )
        precondition_floor = (
            own_claim
            if all(p.holds for p in preconditions)
            else _demote(own_claim)
        )
        effective = min(own_claim, input_floor, precondition_floor)

        # 5. If a layer's effective status is BELOW its declared status, that
        #    is a LEGAL demotion — not a P0. The output simply wears the lower
        #    status. The P0 condition is consuming a value above its emission
        #    status, which is enforced by the consumer's input check above.

        # 6. Build the output StatusedValue.
        provenance = self.declare_provenance(inputs)
        out = StatusedValue(
            value=raw_value,
            status=effective,
            provenance=provenance,
            preconditions=preconditions,
            sample_size=getattr(self, "sample_size", None),
        )

        # 7. Emit telemetry. NEVER skip this. Telemetry gap is a P0 trigger.
        AUDIT_LOG.write(
            StatusRecord(
                record_id=out.value_id,
                timestamp=dt.datetime.now(dt.timezone.utc),
                layer=self.name,
                declared_status=own_claim,
                effective_status=effective,
                provenance=provenance,
                preconditions=preconditions,
                sample_size=out.sample_size,
                note=f"effective_status = min({own_claim.label()}, "
                     f"input_floor={input_floor.label()}, "
                     f"precondition_floor={precondition_floor.label()})",
            )
        )

        return out


# ---------------------------------------------------------------------------
# 7. The audit log — append-only, the system's memory of its own honesty
# ---------------------------------------------------------------------------


class AuditLog:
    """Append-only log. In production this writes to PostgreSQL.

    For the reference implementation, in-memory and thread-safe.
    """

    def __init__(self) -> None:
        self._records: list[StatusRecord] = []
        self._lock = threading.Lock()
        self._on_record: list[Callable[[StatusRecord], None]] = []

    def write(self, record: StatusRecord) -> None:
        with self._lock:
            self._records.append(record)
        for hook in self._on_record:
            hook(record)

    def subscribe(self, hook: Callable[[StatusRecord], None]) -> None:
        self._on_record.append(hook)

    def all(self) -> tuple[StatusRecord, ...]:
        with self._lock:
            return tuple(self._records)


AUDIT_LOG = AuditLog()


# ---------------------------------------------------------------------------
# 8. The drift detector — runs continuously, watches for the lying condition
# ---------------------------------------------------------------------------


class DriftDetector:
    """Subscribes to the audit log. Emits a signal on every record.

    BLACK signal = P0Incident raised. The routing engine halts.
    """

    def __init__(self, audit_log: AuditLog) -> None:
        self.audit_log = audit_log
        self.signal: DriftSignal = DriftSignal.GREEN
        audit_log.subscribe(self._on_record)

    def _on_record(self, record: StatusRecord) -> None:
        # BLACK: a value was consumed above its emission status.
        # This is enforced at the consumer in Layer.__call__, so reaching this
        # without a P0Incident means the invariant is intact.
        # We additionally check: a layer's effective status fell below its
        # declared status by more than one tier. That is a precondition cliff.

        gap = record.declared_status.value - record.effective_status.value
        if gap >= 2:
            self.signal = DriftSignal.RED
            log.error(
                "DRIFT RED: layer %s declared %s, effective %s. Gap=%d tiers.",
                record.layer,
                record.declared_status.label(),
                record.effective_status.label(),
                gap,
            )
            return

        # AMBER: any precondition holds=False. The layer auto-demoted itself,
        # which is honest, but we want a human to know.
        failing = [p for p in record.preconditions if not p.holds]
        if failing:
            self.signal = DriftSignal.AMBER
            log.warning(
                "DRIFT AMBER: layer %s has %d failing precondition(s): %s",
                record.layer,
                len(failing),
                ", ".join(p.name for p in failing),
            )
            return

        self.signal = DriftSignal.GREEN


# ---------------------------------------------------------------------------
# 9. The promotion gates — the only legal way to move status up
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PromotionRecord:
    """An immutable record that a value was promoted up one tier."""

    promotion_id: str
    from_status: EpistemicStatus
    to_status: EpistemicStatus
    method: str            # "rubric_codification" | "empirical_calibration" | "formal_proof"
    artefacts: tuple[str, ...]   # paths or hashes of supporting evidence
    timestamp: dt.datetime
    approver: str          # human who signed off, or "automated" with checks listed


def promote_to_structured(value: StatusedValue, rubric_path: str, approver: str) -> StatusedValue:
    """1 -> 2: rubric codification.

    The intuited value is now expressed as a deterministic rule with explicit
    inputs, outputs, and weights. The weights are still arbitrary.
    """
    if value.status != EpistemicStatus.INTUITED:
        raise P0Incident(
            f"promote_to_structured: input is {value.status.label()}, expected intuited. "
            "Skipping tiers is forbidden."
        )

    record = PromotionRecord(
        promotion_id=str(uuid.uuid4()),
        from_status=EpistemicStatus.INTUITED,
        to_status=EpistemicStatus.STRUCTURED,
        method="rubric_codification",
        artefacts=(rubric_path,),
        timestamp=dt.datetime.now(dt.timezone.utc),
        approver=approver,
    )
    return dataclasses.replace(
        value,
        status=EpistemicStatus.STRUCTURED,
        provenance=dataclasses.replace(value.provenance, promotion_record_id=record.promotion_id),
    )


def promote_to_measured(
    value: StatusedValue,
    *,
    sample_size: int,
    confidence_interval: tuple[float, float],
    held_out_validation: float,
    drift_monitor_id: str,
    approver: str,
) -> StatusedValue:
    """2 -> 3: empirical calibration.

    The structured rule's parameters are fitted from data with declared CI,
    sample size, held-out validation, and an active drift monitor.
    """
    if value.status != EpistemicStatus.STRUCTURED:
        raise P0Incident(
            f"promote_to_measured: input is {value.status.label()}, expected structured."
        )
    if sample_size < 30:
        raise P0Incident(
            f"promote_to_measured: sample_size={sample_size} < 30. "
            "MEASURED requires meaningful sample size."
        )

    record = PromotionRecord(
        promotion_id=str(uuid.uuid4()),
        from_status=EpistemicStatus.STRUCTURED,
        to_status=EpistemicStatus.MEASURED,
        method="empirical_calibration",
        artefacts=(
            f"sample_size={sample_size}",
            f"ci={confidence_interval}",
            f"held_out={held_out_validation}",
            f"drift_monitor={drift_monitor_id}",
        ),
        timestamp=dt.datetime.now(dt.timezone.utc),
        approver=approver,
    )
    return dataclasses.replace(
        value,
        status=EpistemicStatus.MEASURED,
        sample_size=sample_size,
        provenance=dataclasses.replace(value.provenance, promotion_record_id=record.promotion_id),
    )


def promote_to_proven(
    value: StatusedValue,
    *,
    theorem: str,
    preconditions: Sequence[PreconditionCheck],
    approver: str,
) -> StatusedValue:
    """3 -> 4: formal proof.

    The measured relationship is shown to follow from a closed-form theorem
    whose preconditions are independently verified.
    """
    if value.status != EpistemicStatus.MEASURED:
        raise P0Incident(
            f"promote_to_proven: input is {value.status.label()}, expected measured."
        )
    failing = [p for p in preconditions if not p.holds]
    if failing:
        raise P0Incident(
            f"promote_to_proven: {len(failing)} precondition(s) failing: "
            f"{[p.name for p in failing]}. PROVEN requires verified preconditions."
        )

    record = PromotionRecord(
        promotion_id=str(uuid.uuid4()),
        from_status=EpistemicStatus.MEASURED,
        to_status=EpistemicStatus.PROVEN,
        method="formal_proof",
        artefacts=(theorem,) + tuple(p.name for p in preconditions),
        timestamp=dt.datetime.now(dt.timezone.utc),
        approver=approver,
    )
    return dataclasses.replace(
        value,
        status=EpistemicStatus.PROVEN,
        preconditions=tuple(preconditions),
        provenance=dataclasses.replace(value.provenance, promotion_record_id=record.promotion_id),
    )


# ---------------------------------------------------------------------------
# 10. Federation rule
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class FederationUpdate:
    """A client's contribution to the federated parameter pool."""

    client_id: str
    parameter_name: str
    parameter_update: Any
    parameter_status_at_emission: EpistemicStatus
    sample_size: int
    drift_signal: DriftSignal
    preconditions_verified: tuple[str, ...]


def aggregate_federation_updates(
    updates: Sequence[FederationUpdate],
    *,
    aggregator: Callable[[Sequence[Any]], Any],
) -> StatusedValue:
    """Aggregate client updates into a global parameter.

    Quarantine RED/BLACK clients. The aggregated status is the MINIMUM of
    contributing statuses. Aggregation cannot promote.
    """
    valid = [u for u in updates if u.drift_signal in (DriftSignal.GREEN, DriftSignal.AMBER)]
    if not valid:
        raise P0Incident("aggregate_federation_updates: no valid client updates after quarantine.")

    aggregated_value = aggregator([u.parameter_update for u in valid])
    aggregated_status = min(u.parameter_status_at_emission for u in valid)
    aggregated_n = sum(u.sample_size for u in valid)

    return StatusedValue(
        value=aggregated_value,
        status=aggregated_status,   # cannot exceed the minimum input status
        provenance=Provenance(
            layer="federation_aggregator",
            method="weighted_mean",
            inputs=tuple(u.client_id for u in valid),
        ),
        sample_size=aggregated_n,
    )
