"""Vellum Ingestion Gate — correct or reject.

This is the hard gate. Everything that wants to enter Vellum passes through
here. There is no bypass. There is no "close enough." There is no partial
acceptance.

The gate checks:
1. Is the (writer_type, record_type) combination registered? No → REJECT.
2. Does the submission satisfy the proforma fields? No → REJECT.
3. Is the claimed epistemic tier within the proforma ceiling? No → REJECT (or demote).
4. Is signature present when required? No → REJECT.
5. Is provenance present when required? No → REJECT.
6. Is work_packet_id present when required? No → REJECT.

If all pass:
- Assign effective tier (min of claimed and ceiling)
- Sign the record (hash chain)
- Return ACCEPTED verdict + signed record

Devon-b5dc | 2026-05-14
"""

from __future__ import annotations

import datetime as dt
import uuid

from vellum.gate.models import EpistemicStatus
from vellum.ingestion.models import (
    GateVerdict,
    Proforma,
    ProformaField,
    SignedRecord,
    Submission,
)
from vellum.ingestion.registry import ProformaRegistry


# ---------------------------------------------------------------------------
# Field validation — does the payload satisfy the proforma?
# ---------------------------------------------------------------------------


def _validate_field(field: ProformaField, value: object) -> list[str]:
    """Validate a single field value against its proforma definition.

    Returns a list of reason codes (empty = passes).
    """
    reasons: list[str] = []

    if value is None:
        if field.required:
            reasons.append(f"MISSING_REQUIRED_FIELD:{field.name}")
        return reasons

    # Type checks
    type_map = {
        "str": str,
        "int": int,
        "float": (int, float),
        "bool": bool,
        "list": list,
        "dict": dict,
        "datetime": (str, dt.datetime),
    }

    expected = type_map.get(field.field_type)
    if expected and not isinstance(value, expected):
        reasons.append(f"WRONG_TYPE:{field.name}:expected_{field.field_type}")
        return reasons

    # Constraint checks
    if field.max_length is not None and isinstance(value, str) and len(value) > field.max_length:
        reasons.append(f"EXCEEDS_MAX_LENGTH:{field.name}:{len(value)}>{field.max_length}")

    if field.min_value is not None and isinstance(value, (int, float)) and value < field.min_value:
        reasons.append(f"BELOW_MIN_VALUE:{field.name}:{value}<{field.min_value}")

    if field.max_value is not None and isinstance(value, (int, float)) and value > field.max_value:
        reasons.append(f"ABOVE_MAX_VALUE:{field.name}:{value}>{field.max_value}")

    if field.allowed_values is not None and isinstance(value, str) and value not in field.allowed_values:
        reasons.append(f"INVALID_VALUE:{field.name}:{value}:allowed={field.allowed_values}")

    return reasons


def _validate_payload(proforma: Proforma, payload: dict[str, object]) -> list[str]:
    """Validate entire payload against proforma fields.

    Returns all reason codes (empty = payload is valid).
    """
    reasons: list[str] = []

    for field in proforma.fields:
        value = payload.get(field.name)
        reasons.extend(_validate_field(field, value))

    return reasons


# ---------------------------------------------------------------------------
# The Gate — the single entry point.
# ---------------------------------------------------------------------------


class IngestionGate:
    """The hard gate. Correct or reject.

    Stateful: maintains the hash chain (previous_hash).
    The chain ensures no record can be inserted or removed after the fact.
    """

    GENESIS_HASH = "0" * 64  # The first record chains from all-zeros.

    def __init__(self, registry: ProformaRegistry) -> None:
        self._registry = registry
        self._previous_hash: str = self.GENESIS_HASH
        self._record_count: int = 0

    @property
    def previous_hash(self) -> str:
        return self._previous_hash

    @property
    def record_count(self) -> int:
        return self._record_count

    def evaluate(self, submission: Submission) -> tuple[GateVerdict, SignedRecord | None]:
        """Evaluate a submission. Returns (verdict, signed_record or None).

        If ACCEPTED: verdict.decision == "ACCEPTED" and signed_record is not None.
        If REJECTED: verdict.decision == "REJECTED" and signed_record is None.
        reason_codes explain every rejection.
        """
        reasons: list[str] = []
        now = dt.datetime.now(dt.timezone.utc)

        # --- Gate 1: Is this combination registered? ---
        proforma = self._registry.get(submission.writer_type, submission.record_type)
        if proforma is None:
            reasons.append(
                f"UNREGISTERED_TYPE:{submission.writer_type.value}/{submission.record_type}"
            )
            return (
                GateVerdict(
                    submission_id=submission.submission_id,
                    decision="REJECTED",
                    reason_codes=reasons,
                    effective_tier=EpistemicStatus.INTUITED,
                    evaluated_at=now,
                ),
                None,
            )

        # --- Gate 2: Does payload satisfy the proforma? ---
        field_reasons = _validate_payload(proforma, submission.payload)
        reasons.extend(field_reasons)

        # --- Gate 3: Epistemic tier ceiling ---
        if submission.claimed_epistemic_tier > proforma.max_epistemic_tier:
            reasons.append(
                f"TIER_EXCEEDS_CEILING:claimed={submission.claimed_epistemic_tier.label()}"
                f":ceiling={proforma.max_epistemic_tier.label()}"
            )

        # --- Gate 4: Signature ---
        if proforma.requires_signature and not submission.signature:
            reasons.append("MISSING_SIGNATURE")

        # --- Gate 5: Provenance ---
        if proforma.requires_provenance and not submission.provenance:
            reasons.append("MISSING_PROVENANCE")

        # --- Gate 6: Work packet ID ---
        if proforma.requires_work_packet_id and not submission.work_packet_id:
            reasons.append("MISSING_WORK_PACKET_ID")

        # --- Decision ---
        if reasons:
            return (
                GateVerdict(
                    submission_id=submission.submission_id,
                    decision="REJECTED",
                    reason_codes=reasons,
                    effective_tier=EpistemicStatus.INTUITED,
                    evaluated_at=now,
                ),
                None,
            )

        # --- ACCEPTED: assign effective tier and sign ---
        effective_tier = min(submission.claimed_epistemic_tier, proforma.max_epistemic_tier)

        signed_at = now
        record_hash = SignedRecord.compute_hash(
            submission_id=submission.submission_id,
            record_type=submission.record_type,
            author=submission.author,
            payload=submission.payload,
            assigned_tier=effective_tier,
            previous_hash=self._previous_hash,
            signed_at=signed_at,
        )

        record = SignedRecord(
            record_id=str(uuid.uuid4()),
            submission_id=submission.submission_id,
            writer_type=submission.writer_type,
            record_type=submission.record_type,
            author=submission.author,
            session_id=submission.session_id,
            work_packet_id=submission.work_packet_id,
            provenance=submission.provenance,
            payload=submission.payload,
            assigned_tier=effective_tier,
            signed_at=signed_at,
            previous_hash=self._previous_hash,
            record_hash=record_hash,
        )

        # Update chain state
        self._previous_hash = record_hash
        self._record_count += 1

        verdict = GateVerdict(
            submission_id=submission.submission_id,
            decision="ACCEPTED",
            reason_codes=[],
            effective_tier=effective_tier,
            evaluated_at=now,
        )

        return (verdict, record)
