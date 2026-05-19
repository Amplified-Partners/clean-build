"""Tests for brain-migration guardrails — PR 4.

Covers the five required test categories from IMPLEMENTATION_PLAN.md:
  1. INTUITED content excluded from default results
  2. PII-containing results are stripped/tokenised
  3. Permission block enforced at retrieval boundary (purpose scoping)
  4. CRM direct access is blocked outside privileged adapters
  5. Forbidden uses denied

Plus: freshness filter, combined pipeline, edge cases.

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import sys
from pathlib import Path

# Ensure brain-migration is importable
_BRAIN_MIG = Path(__file__).resolve().parent.parent
if str(_BRAIN_MIG) not in sys.path:
    sys.path.insert(0, str(_BRAIN_MIG))

from guardrails import (  # noqa: E402
    CRMAccessDenied,
    apply_guardrails,
    crm_adapter_query,
    filter_by_purpose,
    filter_by_tier,
    filter_expired,
    strip_pii,
    tier_rank,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _row(tier: str = "STRUCTURED", **kw: object) -> dict:
    base: dict = {"id": "r1", "content": "test content", "epistemic_tier": tier}
    base.update(kw)
    return base


# ===================================================================
# 1. Tier filter — INTUITED excluded by default
# ===================================================================


class TestTierFilter:
    def test_intuited_excluded_by_default(self) -> None:
        rows = [_row("INTUITED"), _row("STRUCTURED"), _row("MEASURED")]
        result = filter_by_tier(rows)
        tiers = [r["epistemic_tier"] for r in result]
        assert "INTUITED" not in tiers
        assert "STRUCTURED" in tiers
        assert "MEASURED" in tiers

    def test_all_valid_tiers_ranked(self) -> None:
        for tier in ("INTUITED", "STRUCTURED", "MEASURED", "PROVEN"):
            assert tier_rank(tier) > 0

    def test_higher_min_tier_filters_more(self) -> None:
        rows = [_row("INTUITED"), _row("STRUCTURED"), _row("MEASURED")]
        result = filter_by_tier(rows, min_tier="MEASURED")
        assert len(result) == 1
        assert result[0]["epistemic_tier"] == "MEASURED"

    def test_untiered_excluded_by_default(self) -> None:
        rows = [_row("STRUCTURED"), {"id": "r2", "content": "no tier"}]
        result = filter_by_tier(rows)
        assert len(result) == 1

    def test_untiered_included_when_opted_in(self) -> None:
        rows = [_row("STRUCTURED"), {"id": "r2", "content": "no tier"}]
        result = filter_by_tier(rows, include_untiered=True)
        assert len(result) == 2

    def test_empty_tier_string_excluded(self) -> None:
        rows = [_row(""), _row("STRUCTURED")]
        result = filter_by_tier(rows)
        assert len(result) == 1

    def test_custom_tier_field(self) -> None:
        rows = [{"tier": "MEASURED"}, {"tier": "INTUITED"}]
        result = filter_by_tier(rows, tier_field="tier")
        assert len(result) == 1

    def test_proven_always_included(self) -> None:
        rows = [_row("PROVEN")]
        result = filter_by_tier(rows, min_tier="PROVEN")
        assert len(result) == 1

    def test_empty_input_returns_empty(self) -> None:
        assert filter_by_tier([]) == []


# ===================================================================
# 2. PII filter — strip/tokenise PII fields
# ===================================================================


class TestPIIFilter:
    def test_named_pii_fields_redacted(self) -> None:
        rows = [{"id": "1", "email": "bob@example.com", "phone": "07700900000", "content": "safe"}]
        result = strip_pii(rows)
        assert result[0]["email"] == "[PII_REDACTED]"
        assert result[0]["phone"] == "[PII_REDACTED]"
        assert result[0]["content"] == "safe"

    def test_inline_email_redacted(self) -> None:
        rows = [{"id": "1", "notes": "Contact bob@example.com for details"}]
        result = strip_pii(rows)
        assert "bob@example.com" not in result[0]["notes"]
        assert "[PII_REDACTED]" in result[0]["notes"]

    def test_inline_phone_redacted(self) -> None:
        rows = [{"id": "1", "notes": "Call +44 7700 900000 today"}]
        result = strip_pii(rows)
        assert "7700" not in result[0]["notes"]

    def test_inline_postcode_redacted(self) -> None:
        rows = [{"id": "1", "notes": "Located at NE1 4LP in Newcastle"}]
        result = strip_pii(rows)
        assert "NE1 4LP" not in result[0]["notes"]

    def test_non_string_values_untouched(self) -> None:
        rows = [{"id": "1", "count": 42, "active": True}]
        result = strip_pii(rows)
        assert result[0]["count"] == 42
        assert result[0]["active"] is True

    def test_redact_inline_can_be_disabled(self) -> None:
        rows = [{"id": "1", "notes": "Contact bob@example.com"}]
        result = strip_pii(rows, redact_inline=False)
        assert "bob@example.com" in result[0]["notes"]

    def test_address_field_redacted(self) -> None:
        rows = [{"id": "1", "address": "10 Downing St", "content": "safe"}]
        result = strip_pii(rows)
        assert result[0]["address"] == "[PII_REDACTED]"

    def test_multiple_pii_in_one_string(self) -> None:
        rows = [{"id": "1", "bio": "bob@x.com lives at NE1 4LP call 07700900000"}]
        result = strip_pii(rows)
        assert "bob@x.com" not in result[0]["bio"]
        assert "NE1 4LP" not in result[0]["bio"]

    def test_empty_input(self) -> None:
        assert strip_pii([]) == []


# ===================================================================
# 3. Purpose scoping — forbidden uses denied
# ===================================================================


class TestPurposeScoping:
    def test_allowed_purpose_passes(self) -> None:
        rows = [_row(allowed_uses=["agent_retrieval", "research"])]
        result = filter_by_purpose(rows, purpose="agent_retrieval")
        assert len(result) == 1

    def test_disallowed_purpose_filtered(self) -> None:
        rows = [_row(allowed_uses=["research"])]
        result = filter_by_purpose(rows, purpose="marketing")
        assert len(result) == 0

    def test_forbidden_purpose_filtered(self) -> None:
        rows = [_row(forbidden_uses=["marketing"])]
        result = filter_by_purpose(rows, purpose="marketing")
        assert len(result) == 0

    def test_no_restrictions_passes_all(self) -> None:
        rows = [_row()]
        result = filter_by_purpose(rows, purpose="anything")
        assert len(result) == 1

    def test_forbidden_overrides_allowed(self) -> None:
        rows = [_row(allowed_uses=["marketing"], forbidden_uses=["marketing"])]
        result = filter_by_purpose(rows, purpose="marketing")
        assert len(result) == 0

    def test_multiple_rows_mixed(self) -> None:
        rows = [
            _row(id="ok", allowed_uses=["agent_retrieval"]),
            _row(id="blocked", forbidden_uses=["agent_retrieval"]),
        ]
        result = filter_by_purpose(rows, purpose="agent_retrieval")
        assert len(result) == 1
        assert result[0]["id"] == "ok"


# ===================================================================
# 4. CRM direct access blocked
# ===================================================================


class TestCRMAdapter:
    def test_unprivileged_access_denied(self) -> None:
        with pytest.raises(CRMAccessDenied, match="Direct CRM access denied"):
            crm_adapter_query(purpose="agent_retrieval", fields=["name"])

    def test_privileged_access_returns_stub(self) -> None:
        result = crm_adapter_query(
            purpose="agent_retrieval", fields=["name", "email"], privileged=True
        )
        assert result["status"] == "stub"
        assert result["purpose"] == "agent_retrieval"
        assert result["fields_requested"] == ["name", "email"]

    def test_default_is_unprivileged(self) -> None:
        with pytest.raises(CRMAccessDenied):
            crm_adapter_query(purpose="research", fields=["revenue"])


# ===================================================================
# 5. Freshness filter — expired content excluded
# ===================================================================


class TestFreshnessFilter:
    def test_expired_content_excluded(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(days=1)
        rows = [_row(valid_until=past)]
        result = filter_expired(rows)
        assert len(result) == 0

    def test_future_content_included(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(days=30)
        rows = [_row(valid_until=future)]
        result = filter_expired(rows)
        assert len(result) == 1

    def test_no_expiry_included(self) -> None:
        rows = [_row()]
        result = filter_expired(rows)
        assert len(result) == 1

    def test_iso_string_parsed(self) -> None:
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        rows = [_row(valid_until=future)]
        result = filter_expired(rows)
        assert len(result) == 1

    def test_expired_iso_string_excluded(self) -> None:
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        rows = [_row(valid_until=past)]
        result = filter_expired(rows)
        assert len(result) == 0

    def test_custom_now(self) -> None:
        fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        expiry = datetime(2025, 12, 31, tzinfo=timezone.utc)
        rows = [_row(valid_until=expiry)]
        result = filter_expired(rows, now=fixed)
        assert len(result) == 0

    def test_naive_datetime_treated_as_utc(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(days=30)
        naive_future = future.replace(tzinfo=None)
        rows = [_row(valid_until=naive_future)]
        result = filter_expired(rows)
        assert len(result) == 1

    def test_invalid_string_passes_through(self) -> None:
        rows = [_row(valid_until="not-a-date")]
        result = filter_expired(rows)
        assert len(result) == 1


# ===================================================================
# 6. Combined pipeline — apply_guardrails
# ===================================================================


class TestApplyGuardrails:
    def test_full_pipeline(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(days=1)
        rows = [
            _row("MEASURED", id="good", content="Clean data"),
            _row("INTUITED", id="low_tier"),
            _row("STRUCTURED", id="expired", valid_until=past),
            _row("STRUCTURED", id="forbidden", forbidden_uses=["agent_retrieval"]),
            _row("STRUCTURED", id="pii", email="bob@test.com"),
        ]
        result = apply_guardrails(rows, purpose="agent_retrieval")
        ids = [r["id"] for r in result]
        assert "good" in ids
        assert "low_tier" not in ids
        assert "expired" not in ids
        assert "forbidden" not in ids
        assert "pii" in ids
        pii_row = [r for r in result if r["id"] == "pii"][0]
        assert pii_row["email"] == "[PII_REDACTED]"

    def test_default_purpose(self) -> None:
        rows = [_row("MEASURED")]
        result = apply_guardrails(rows)
        assert len(result) == 1

    def test_all_filters_can_be_configured(self) -> None:
        rows = [_row("INTUITED")]
        result = apply_guardrails(
            rows,
            min_tier="INTUITED",
            strip_pii_fields=False,
            check_freshness=False,
        )
        assert len(result) == 1

    def test_empty_input(self) -> None:
        assert apply_guardrails([]) == []
