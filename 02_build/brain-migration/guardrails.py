"""Brain MCP Gateway Guardrails — PR 4.

Enforces governed access to Brain retrieval results:
  - Tier filter: exclude INTUITED from default retrieval (configurable)
  - PII filter: strip/tokenise PII fields before returning
  - Purpose scoping: callers declare ``purpose``; forbidden uses denied
  - Freshness filter: exclude expired content (valid_until check)

These guardrails sit between the raw database results and what gets
returned to MCP tool callers. They are pure functions — no database
access, no side effects, easy to test.

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from epistemic_core.tiers import TIER_RANK

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Minimum tier for default retrieval. Content below this tier is excluded
# unless the caller explicitly opts in with include_intuited=True.
DEFAULT_MIN_TIER: str = "STRUCTURED"

# Fields that may contain PII and should be stripped/tokenised
PII_FIELDS: frozenset[str] = frozenset({
    "email", "phone", "address", "postcode", "post_code",
    "name", "full_name", "first_name", "last_name",
    "contact_name", "contact_email", "contact_phone",
    "national_insurance", "ni_number", "date_of_birth", "dob",
    "bank_account", "sort_code", "account_number",
})

# Regex patterns for inline PII detection
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"\+?[\d\s\-()]{10,15}")
_POSTCODE_RE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.IGNORECASE)

_PII_TOKEN = "[PII_REDACTED]"


# ---------------------------------------------------------------------------
# Tier filter
# ---------------------------------------------------------------------------


def tier_rank(tier_str: str) -> int:
    """Return numeric rank for a tier string (0 if unknown)."""
    return TIER_RANK.get(tier_str.upper().strip(), 0) if tier_str else 0


def filter_by_tier(
    results: list[dict[str, Any]],
    *,
    min_tier: str = DEFAULT_MIN_TIER,
    tier_field: str = "epistemic_tier",
    include_untiered: bool = False,
) -> list[dict[str, Any]]:
    """Exclude results below the minimum epistemic tier.

    Results without a tier field are excluded unless include_untiered=True.
    """
    min_rank = tier_rank(min_tier)
    out: list[dict[str, Any]] = []
    for row in results:
        raw_tier = row.get(tier_field)
        if raw_tier is None or raw_tier == "":
            if include_untiered:
                out.append(row)
            continue
        if tier_rank(str(raw_tier)) >= min_rank:
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# PII filter
# ---------------------------------------------------------------------------


def _redact_inline_pii(text: str) -> str:
    """Replace inline email, phone, and postcode patterns with token."""
    text = _EMAIL_RE.sub(_PII_TOKEN, text)
    text = _PHONE_RE.sub(_PII_TOKEN, text)
    text = _POSTCODE_RE.sub(_PII_TOKEN, text)
    return text


def strip_pii(
    results: list[dict[str, Any]],
    *,
    pii_fields: frozenset[str] = PII_FIELDS,
    redact_inline: bool = True,
) -> list[dict[str, Any]]:
    """Strip or tokenise PII fields from result dicts.

    - Named PII fields are replaced with the redaction token
    - If redact_inline is True, string values in all fields are scanned
      for email/phone/postcode patterns and redacted
    """
    out: list[dict[str, Any]] = []
    for row in results:
        clean: dict[str, Any] = {}
        for key, val in row.items():
            if key.lower() in pii_fields:
                clean[key] = _PII_TOKEN
            elif redact_inline and isinstance(val, str):
                clean[key] = _redact_inline_pii(val)
            else:
                clean[key] = val
        out.append(clean)
    return out


# ---------------------------------------------------------------------------
# Purpose scoping
# ---------------------------------------------------------------------------


def filter_by_purpose(
    results: list[dict[str, Any]],
    *,
    purpose: str,
    allowed_field: str = "allowed_uses",
    forbidden_field: str = "forbidden_uses",
) -> list[dict[str, Any]]:
    """Exclude results whose permission metadata forbids the stated purpose.

    A result is included if:
      - It has no allowed_uses field (no restriction), OR
      - purpose is in allowed_uses
    AND:
      - purpose is NOT in forbidden_uses (if present)
    """
    out: list[dict[str, Any]] = []
    for row in results:
        forbidden = row.get(forbidden_field)
        if isinstance(forbidden, list) and purpose in forbidden:
            continue

        allowed = row.get(allowed_field)
        if isinstance(allowed, list) and purpose not in allowed:
            continue

        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Freshness filter
# ---------------------------------------------------------------------------


def filter_expired(
    results: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    valid_until_field: str = "valid_until",
) -> list[dict[str, Any]]:
    """Exclude results whose valid_until timestamp has passed.

    Results without a valid_until field are assumed still-valid (no expiry).
    """
    check_time = now or datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    for row in results:
        valid_until = row.get(valid_until_field)
        if valid_until is None:
            out.append(row)
            continue
        if isinstance(valid_until, str):
            try:
                valid_until = datetime.fromisoformat(valid_until)
            except (ValueError, TypeError):
                out.append(row)
                continue
        if isinstance(valid_until, datetime):
            if valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=timezone.utc)
            if valid_until > check_time:
                out.append(row)
        else:
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# CRM adapter interface
# ---------------------------------------------------------------------------


class CRMAccessDenied(Exception):
    """Raised when direct CRM access is attempted outside privileged adapters."""

    pass


def crm_adapter_query(
    *,
    purpose: str,
    fields: list[str],
    privileged: bool = False,
) -> dict[str, Any]:
    """CRM adapter interface stub.

    Returns permission-safe, PII-minimised, purpose-scoped data.
    Direct CRM access is denied unless explicitly privileged.

    This is a stub — the actual implementation will call the CRM API
    when the CRM is deployed to Beast. For now it enforces the access
    boundary and returns a structured response.
    """
    if not privileged:
        raise CRMAccessDenied(
            "Direct CRM access denied. Use the Brain MCP gateway with "
            "a declared purpose. Raw CRM queries require explicit privilege."
        )
    return {
        "status": "stub",
        "purpose": purpose,
        "fields_requested": fields,
        "note": "CRM not yet deployed to Beast. Adapter interface ready.",
    }


# ---------------------------------------------------------------------------
# Combined guardrail pipeline
# ---------------------------------------------------------------------------


def apply_guardrails(
    results: list[dict[str, Any]],
    *,
    purpose: str = "agent_retrieval",
    min_tier: str = DEFAULT_MIN_TIER,
    tier_field: str = "epistemic_tier",
    include_untiered: bool = False,
    strip_pii_fields: bool = True,
    check_freshness: bool = True,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Apply all guardrails in sequence: tier → purpose → freshness → PII.

    This is the single entry point for governed retrieval. All Brain MCP
    tool results should pass through this before being returned to callers.
    """
    filtered = filter_by_tier(
        results, min_tier=min_tier, tier_field=tier_field,
        include_untiered=include_untiered,
    )
    filtered = filter_by_purpose(filtered, purpose=purpose)
    if check_freshness:
        filtered = filter_expired(filtered, now=now)
    if strip_pii_fields:
        filtered = strip_pii(filtered)
    return filtered
