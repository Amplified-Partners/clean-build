"""Tests for the Vellum Ingestion Gate.

Covers:
- Valid submissions pass (ACCEPTED + signed record)
- Invalid submissions fail (REJECTED + reason codes)
- Each gate check independently
- Hash chain integrity
- Tier ceiling enforcement (min-rule)
- Proforma registry behaviour

Devon-b5dc | 2026-05-14
"""

from __future__ import annotations

import datetime as dt

import pytest

from vellum.gate.models import EpistemicStatus
from vellum.ingestion.gate import IngestionGate, _validate_field
from vellum.ingestion.models import (
    Proforma,
    ProformaField,
    SignedRecord,
    Submission,
    WriterType,
)
from vellum.ingestion.registry import ProformaRegistry, build_default_registry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry() -> ProformaRegistry:
    return build_default_registry()


@pytest.fixture
def gate(registry: ProformaRegistry) -> IngestionGate:
    return IngestionGate(registry)


def _make_agent_completion(
    submission_id: str = "sub-001",
    work_packet_id: str = "wp-001",
    claimed_tier: EpistemicStatus = EpistemicStatus.STRUCTURED,
    signature: str | None = "Devon-b5dc | 2026-05-14 | devin-abc123",
    provenance: str | None = "PR #140 merged",
    payload: dict | None = None,
) -> Submission:
    """Helper: build a valid agent completion_report submission."""
    if payload is None:
        payload = {
            "task_id": "AMP-115",
            "summary": "Built pattern transfer gate with min-rule enforcement.",
            "artefacts": ["https://github.com/Amplified-Partners/clean-build/pull/140"],
            "tests_passed": True,
            "unresolved_risks": [],
        }
    return Submission(
        submission_id=submission_id,
        writer_type=WriterType.AGENT,
        record_type="completion_report",
        claimed_epistemic_tier=claimed_tier,
        author="Devon-b5dc",
        session_id="devin-abc123",
        work_packet_id=work_packet_id,
        provenance=provenance,
        payload=payload,
        signature=signature,
    )


def _make_human_decision(
    submission_id: str = "sub-002",
    signature: str | None = "Ewan | 2026-05-14",
    provenance: str | None = "verbal direction",
) -> Submission:
    """Helper: build a valid human decision submission."""
    return Submission(
        submission_id=submission_id,
        writer_type=WriterType.HUMAN,
        record_type="decision",
        claimed_epistemic_tier=EpistemicStatus.STRUCTURED,
        author="Ewan",
        provenance=provenance,
        payload={
            "decision": "Vellum is its own thing. Code or gone.",
            "context": "Verbal confirmation during morning session.",
            "reversible": False,
        },
        signature=signature,
    )


def _make_sensor_telemetry(
    submission_id: str = "sub-003",
) -> Submission:
    """Helper: build a valid sensor telemetry submission."""
    return Submission(
        submission_id=submission_id,
        writer_type=WriterType.SENSOR,
        record_type="telemetry",
        claimed_epistemic_tier=EpistemicStatus.MEASURED,
        author="beast-health-monitor",
        provenance="cron-5min",
        payload={
            "metric_name": "container_count",
            "value": 40.0,
            "unit": "containers",
            "measured_at": "2026-05-14T08:00:00+00:00",
            "source_system": "docker-ps",
        },
    )


# ---------------------------------------------------------------------------
# TestAcceptedSubmissions
# ---------------------------------------------------------------------------


class TestAcceptedSubmissions:
    """Submissions that should pass the gate cleanly."""

    def test_agent_completion_report_accepted(self, gate: IngestionGate) -> None:
        sub = _make_agent_completion()
        verdict, record = gate.evaluate(sub)

        assert verdict.decision == "ACCEPTED"
        assert verdict.reason_codes == []
        assert verdict.effective_tier == EpistemicStatus.STRUCTURED
        assert record is not None
        assert record.submission_id == sub.submission_id
        assert record.author == "Devon-b5dc"
        assert record.assigned_tier == EpistemicStatus.STRUCTURED

    def test_human_decision_accepted(self, gate: IngestionGate) -> None:
        sub = _make_human_decision()
        verdict, record = gate.evaluate(sub)

        assert verdict.decision == "ACCEPTED"
        assert record is not None
        assert record.record_type == "decision"
        assert record.assigned_tier == EpistemicStatus.STRUCTURED

    def test_sensor_telemetry_accepted(self, gate: IngestionGate) -> None:
        sub = _make_sensor_telemetry()
        verdict, record = gate.evaluate(sub)

        assert verdict.decision == "ACCEPTED"
        assert record is not None
        assert record.assigned_tier == EpistemicStatus.MEASURED

    def test_sensor_does_not_require_signature(self, gate: IngestionGate) -> None:
        """Sensor proforma has requires_signature=False."""
        sub = _make_sensor_telemetry()
        sub.signature = None  # No signature
        verdict, record = gate.evaluate(sub)

        assert verdict.decision == "ACCEPTED"
        assert record is not None


# ---------------------------------------------------------------------------
# TestRejectedSubmissions — Gate 1: Unregistered type
# ---------------------------------------------------------------------------


class TestUnregisteredType:
    """Unknown (writer_type, record_type) combinations are rejected."""

    def test_unknown_record_type_rejected(self, gate: IngestionGate) -> None:
        sub = Submission(
            submission_id="sub-unknown",
            writer_type=WriterType.AGENT,
            record_type="fantasy_report",
            claimed_epistemic_tier=EpistemicStatus.STRUCTURED,
            author="Devon-b5dc",
            signature="Devon-b5dc | 2026-05-14",
            provenance="test",
            payload={},
        )
        verdict, record = gate.evaluate(sub)

        assert verdict.decision == "REJECTED"
        assert record is None
        assert any("UNREGISTERED_TYPE" in r for r in verdict.reason_codes)

    def test_unknown_writer_type_combination_rejected(self, gate: IngestionGate) -> None:
        sub = Submission(
            submission_id="sub-bad-combo",
            writer_type=WriterType.HUMAN,
            record_type="telemetry",  # Humans don't submit telemetry
            claimed_epistemic_tier=EpistemicStatus.MEASURED,
            author="Ewan",
            signature="Ewan | 2026-05-14",
            provenance="test",
            payload={},
        )
        verdict, record = gate.evaluate(sub)

        assert verdict.decision == "REJECTED"
        assert any("UNREGISTERED_TYPE" in r for r in verdict.reason_codes)


# ---------------------------------------------------------------------------
# TestRejectedSubmissions — Gate 2: Missing required fields
# ---------------------------------------------------------------------------


class TestMissingFields:
    """Submissions missing required proforma fields are rejected."""

    def test_missing_task_id_rejected(self, gate: IngestionGate) -> None:
        sub = _make_agent_completion(payload={
            # task_id missing
            "summary": "Did something.",
            "artefacts": [],
            "tests_passed": True,
        })
        verdict, record = gate.evaluate(sub)

        assert verdict.decision == "REJECTED"
        assert record is None
        assert any("MISSING_REQUIRED_FIELD:task_id" in r for r in verdict.reason_codes)

    def test_missing_summary_rejected(self, gate: IngestionGate) -> None:
        sub = _make_agent_completion(payload={
            "task_id": "AMP-115",
            # summary missing
            "artefacts": [],
            "tests_passed": True,
        })
        verdict, record = gate.evaluate(sub)

        assert verdict.decision == "REJECTED"
        assert any("MISSING_REQUIRED_FIELD:summary" in r for r in verdict.reason_codes)

    def test_missing_multiple_fields_returns_all_reasons(self, gate: IngestionGate) -> None:
        sub = _make_agent_completion(payload={})
        verdict, _ = gate.evaluate(sub)

        assert verdict.decision == "REJECTED"
        # Should have multiple reason codes (task_id, summary, artefacts, tests_passed)
        assert len(verdict.reason_codes) >= 4


# ---------------------------------------------------------------------------
# TestRejectedSubmissions — Gate 3: Tier ceiling
# ---------------------------------------------------------------------------


class TestTierCeiling:
    """Claimed tier exceeding proforma ceiling is rejected."""

    def test_agent_claiming_proven_rejected(self, gate: IngestionGate) -> None:
        """Agent proforma ceiling is STRUCTURED. Claiming PROVEN is rejected."""
        sub = _make_agent_completion(claimed_tier=EpistemicStatus.PROVEN)
        verdict, _ = gate.evaluate(sub)

        assert verdict.decision == "REJECTED"
        assert any("TIER_EXCEEDS_CEILING" in r for r in verdict.reason_codes)

    def test_agent_claiming_measured_rejected(self, gate: IngestionGate) -> None:
        """Agent completion ceiling is STRUCTURED. MEASURED exceeds it."""
        sub = _make_agent_completion(claimed_tier=EpistemicStatus.MEASURED)
        verdict, _ = gate.evaluate(sub)

        assert verdict.decision == "REJECTED"
        assert any("TIER_EXCEEDS_CEILING" in r for r in verdict.reason_codes)

    def test_sensor_claiming_measured_accepted(self, gate: IngestionGate) -> None:
        """Sensor proforma ceiling is MEASURED. Claiming MEASURED is fine."""
        sub = _make_sensor_telemetry()
        sub.claimed_epistemic_tier = EpistemicStatus.MEASURED
        verdict, record = gate.evaluate(sub)

        assert verdict.decision == "ACCEPTED"
        assert record is not None
        assert record.assigned_tier == EpistemicStatus.MEASURED

    def test_effective_tier_is_min_of_claimed_and_ceiling(self, gate: IngestionGate) -> None:
        """If claimed < ceiling, effective = claimed (min-rule)."""
        sub = _make_agent_completion(claimed_tier=EpistemicStatus.INTUITED)
        verdict, record = gate.evaluate(sub)

        assert verdict.decision == "ACCEPTED"
        assert record is not None
        assert record.assigned_tier == EpistemicStatus.INTUITED


# ---------------------------------------------------------------------------
# TestRejectedSubmissions — Gate 4: Missing signature
# ---------------------------------------------------------------------------


class TestMissingSignature:
    """Submissions missing required signature are rejected."""

    def test_agent_without_signature_rejected(self, gate: IngestionGate) -> None:
        sub = _make_agent_completion(signature=None)
        verdict, _ = gate.evaluate(sub)

        assert verdict.decision == "REJECTED"
        assert "MISSING_SIGNATURE" in verdict.reason_codes

    def test_human_without_signature_rejected(self, gate: IngestionGate) -> None:
        sub = _make_human_decision(signature=None)
        verdict, _ = gate.evaluate(sub)

        assert verdict.decision == "REJECTED"
        assert "MISSING_SIGNATURE" in verdict.reason_codes


# ---------------------------------------------------------------------------
# TestRejectedSubmissions — Gate 5: Missing provenance
# ---------------------------------------------------------------------------


class TestMissingProvenance:
    """Submissions missing required provenance are rejected."""

    def test_agent_without_provenance_rejected(self, gate: IngestionGate) -> None:
        sub = _make_agent_completion(provenance=None)
        verdict, _ = gate.evaluate(sub)

        assert verdict.decision == "REJECTED"
        assert "MISSING_PROVENANCE" in verdict.reason_codes


# ---------------------------------------------------------------------------
# TestRejectedSubmissions — Gate 6: Missing work_packet_id
# ---------------------------------------------------------------------------


class TestMissingWorkPacketId:
    """Submissions missing work_packet_id when required are rejected."""

    def test_agent_completion_without_wp_id_rejected(self, gate: IngestionGate) -> None:
        """Agent completion_report proforma requires work_packet_id."""
        sub = _make_agent_completion(work_packet_id=None)
        # work_packet_id is required for this proforma
        verdict, _ = gate.evaluate(sub)

        assert verdict.decision == "REJECTED"
        assert "MISSING_WORK_PACKET_ID" in verdict.reason_codes


# ---------------------------------------------------------------------------
# TestHashChain — immutability layer 1
# ---------------------------------------------------------------------------


class TestHashChain:
    """Hash chain integrity tests."""

    def test_first_record_chains_from_genesis(self, gate: IngestionGate) -> None:
        sub = _make_agent_completion()
        _, record = gate.evaluate(sub)

        assert record is not None
        assert record.previous_hash == IngestionGate.GENESIS_HASH

    def test_second_record_chains_from_first(self, gate: IngestionGate) -> None:
        sub1 = _make_agent_completion(submission_id="sub-001")
        _, record1 = gate.evaluate(sub1)

        sub2 = _make_human_decision(submission_id="sub-002")
        _, record2 = gate.evaluate(sub2)

        assert record1 is not None
        assert record2 is not None
        assert record2.previous_hash == record1.record_hash

    def test_chain_grows_sequentially(self, gate: IngestionGate) -> None:
        """Three records form a proper chain."""
        subs = [
            _make_agent_completion(submission_id="sub-a"),
            _make_human_decision(submission_id="sub-b"),
            _make_sensor_telemetry(submission_id="sub-c"),
        ]

        records = []
        for sub in subs:
            _, record = gate.evaluate(sub)
            assert record is not None
            records.append(record)

        assert records[0].previous_hash == IngestionGate.GENESIS_HASH
        assert records[1].previous_hash == records[0].record_hash
        assert records[2].previous_hash == records[1].record_hash

    def test_rejected_submission_does_not_advance_chain(self, gate: IngestionGate) -> None:
        """Rejected submissions don't change the hash chain state."""
        # First: accept one
        sub1 = _make_agent_completion(submission_id="sub-good")
        _, record1 = gate.evaluate(sub1)
        hash_after_first = gate.previous_hash

        # Second: reject one (missing field)
        bad_sub = _make_agent_completion(submission_id="sub-bad", payload={})
        verdict, _ = gate.evaluate(bad_sub)
        assert verdict.decision == "REJECTED"

        # Chain hasn't moved
        assert gate.previous_hash == hash_after_first

    def test_record_hash_is_deterministic(self) -> None:
        """Same inputs produce same hash."""
        fixed_time = dt.datetime(2026, 5, 14, 12, 0, 0, tzinfo=dt.timezone.utc)
        payload = {"task_id": "T1", "summary": "x", "artefacts": [], "tests_passed": True}

        hash1 = SignedRecord.compute_hash(
            submission_id="s1",
            record_type="completion_report",
            author="Devon",
            payload=payload,
            assigned_tier=EpistemicStatus.STRUCTURED,
            previous_hash="0" * 64,
            signed_at=fixed_time,
        )
        hash2 = SignedRecord.compute_hash(
            submission_id="s1",
            record_type="completion_report",
            author="Devon",
            payload=payload,
            assigned_tier=EpistemicStatus.STRUCTURED,
            previous_hash="0" * 64,
            signed_at=fixed_time,
        )
        assert hash1 == hash2

    def test_different_content_different_hash(self) -> None:
        """Changing any input changes the hash."""
        fixed_time = dt.datetime(2026, 5, 14, 12, 0, 0, tzinfo=dt.timezone.utc)
        base_args = dict(
            submission_id="s1",
            record_type="completion_report",
            author="Devon",
            payload={"key": "value"},
            assigned_tier=EpistemicStatus.STRUCTURED,
            previous_hash="0" * 64,
            signed_at=fixed_time,
        )

        hash_base = SignedRecord.compute_hash(**base_args)
        hash_diff_author = SignedRecord.compute_hash(**{**base_args, "author": "Ewan"})
        hash_diff_tier = SignedRecord.compute_hash(**{**base_args, "assigned_tier": EpistemicStatus.INTUITED})

        assert hash_base != hash_diff_author
        assert hash_base != hash_diff_tier


# ---------------------------------------------------------------------------
# TestFieldValidation — unit tests for field-level validation
# ---------------------------------------------------------------------------


class TestFieldValidation:
    """Unit tests for _validate_field."""

    def test_required_field_present_passes(self) -> None:
        field = ProformaField(name="x", field_type="str", required=True)
        assert _validate_field(field, "hello") == []

    def test_required_field_missing_fails(self) -> None:
        field = ProformaField(name="x", field_type="str", required=True)
        reasons = _validate_field(field, None)
        assert len(reasons) == 1
        assert "MISSING_REQUIRED_FIELD:x" in reasons[0]

    def test_optional_field_missing_passes(self) -> None:
        field = ProformaField(name="x", field_type="str", required=False)
        assert _validate_field(field, None) == []

    def test_wrong_type_fails(self) -> None:
        field = ProformaField(name="x", field_type="str", required=True)
        reasons = _validate_field(field, 123)
        assert any("WRONG_TYPE" in r for r in reasons)

    def test_max_length_exceeded_fails(self) -> None:
        field = ProformaField(name="x", field_type="str", required=True, max_length=5)
        reasons = _validate_field(field, "toolong")
        assert any("EXCEEDS_MAX_LENGTH" in r for r in reasons)

    def test_max_length_within_passes(self) -> None:
        field = ProformaField(name="x", field_type="str", required=True, max_length=100)
        assert _validate_field(field, "short") == []

    def test_min_value_below_fails(self) -> None:
        field = ProformaField(name="x", field_type="float", required=True, min_value=0.0)
        reasons = _validate_field(field, -1.0)
        assert any("BELOW_MIN_VALUE" in r for r in reasons)

    def test_max_value_above_fails(self) -> None:
        field = ProformaField(name="x", field_type="float", required=True, max_value=1.0)
        reasons = _validate_field(field, 2.5)
        assert any("ABOVE_MAX_VALUE" in r for r in reasons)

    def test_allowed_values_invalid_fails(self) -> None:
        field = ProformaField(name="x", field_type="str", required=True, allowed_values=["a", "b"])
        reasons = _validate_field(field, "c")
        assert any("INVALID_VALUE" in r for r in reasons)

    def test_allowed_values_valid_passes(self) -> None:
        field = ProformaField(name="x", field_type="str", required=True, allowed_values=["a", "b"])
        assert _validate_field(field, "a") == []


# ---------------------------------------------------------------------------
# TestProformaRegistry
# ---------------------------------------------------------------------------


class TestProformaRegistry:
    """Tests for the registry itself."""

    def test_default_registry_has_expected_types(self) -> None:
        reg = build_default_registry()
        types = reg.registered_types()

        assert (WriterType.AGENT, "completion_report") in types
        assert (WriterType.AGENT, "observation") in types
        assert (WriterType.HUMAN, "decision") in types
        assert (WriterType.HUMAN, "plan") in types
        assert (WriterType.TOOL, "status_update") in types
        assert (WriterType.RESEARCH, "finding") in types
        assert (WriterType.SENSOR, "telemetry") in types
        assert (WriterType.ORCHESTRATOR, "workflow_result") in types

    def test_unregistered_returns_none(self) -> None:
        reg = build_default_registry()
        assert reg.get(WriterType.AGENT, "nonexistent") is None

    def test_custom_proforma_can_be_registered(self) -> None:
        reg = ProformaRegistry()
        custom = Proforma(
            proforma_id="custom.test",
            writer_type=WriterType.AGENT,
            record_type="custom_thing",
            fields=[ProformaField(name="x", field_type="str", required=True)],
        )
        reg.register(custom)
        assert reg.get(WriterType.AGENT, "custom_thing") == custom

    def test_registry_length(self) -> None:
        reg = build_default_registry()
        assert len(reg) == 8  # 8 default proformas


# ---------------------------------------------------------------------------
# TestGateInvariants — properties that must always hold
# ---------------------------------------------------------------------------


class TestGateInvariants:
    """Invariants that must hold for any submission, accepted or rejected."""

    def test_verdict_always_has_submission_id(self, gate: IngestionGate) -> None:
        sub = _make_agent_completion()
        verdict, _ = gate.evaluate(sub)
        assert verdict.submission_id == sub.submission_id

    def test_rejected_verdict_always_has_reason_codes(self, gate: IngestionGate) -> None:
        bad = _make_agent_completion(signature=None)
        verdict, _ = gate.evaluate(bad)
        assert verdict.decision == "REJECTED"
        assert len(verdict.reason_codes) > 0

    def test_accepted_verdict_never_has_reason_codes(self, gate: IngestionGate) -> None:
        good = _make_agent_completion()
        verdict, _ = gate.evaluate(good)
        assert verdict.decision == "ACCEPTED"
        assert verdict.reason_codes == []

    def test_record_count_increments_only_on_accept(self, gate: IngestionGate) -> None:
        assert gate.record_count == 0

        # Accept one
        gate.evaluate(_make_agent_completion(submission_id="s1"))
        assert gate.record_count == 1

        # Reject one
        gate.evaluate(_make_agent_completion(submission_id="s2", signature=None))
        assert gate.record_count == 1  # Unchanged

        # Accept another
        gate.evaluate(_make_human_decision(submission_id="s3"))
        assert gate.record_count == 2

    def test_signed_record_hash_is_64_hex_chars(self, gate: IngestionGate) -> None:
        _, record = gate.evaluate(_make_agent_completion())
        assert record is not None
        assert len(record.record_hash) == 64
        assert all(c in "0123456789abcdef" for c in record.record_hash)
