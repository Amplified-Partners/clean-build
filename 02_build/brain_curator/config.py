"""00_config — configuration constants for the brain_curator module.

P0Policy enum, epistemic tier thresholds, route logic thresholds,
and validation sample size. Production default is HALT on any
Layer 0 violation.

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""

from __future__ import annotations

import enum


# ---------------------------------------------------------------------------
# P0 Policy — how the system reacts to Layer 0 violations
# ---------------------------------------------------------------------------


class P0Policy(enum.Enum):
    """Response to epistemic invariant violations.

    HALT is the production default. DEGRADE and TELEMETRY_ONLY exist
    for explicitly labelled experimental/backfill modes only.
    """

    HALT = "halt"
    DEGRADE = "degrade"
    TELEMETRY_ONLY = "telemetry_only"


# Active policy — override only in test fixtures or explicit backfill modes
ACTIVE_P0_POLICY: P0Policy = P0Policy.HALT

# ---------------------------------------------------------------------------
# Module version
# ---------------------------------------------------------------------------

CODE_VERSION = "brain-curator-v0.1"

# ---------------------------------------------------------------------------
# Epistemic tier names (string constants matching DB column values)
# ---------------------------------------------------------------------------

TIER_INTUITED = "INTUITED"
TIER_STRUCTURED = "STRUCTURED"
TIER_MEASURED = "MEASURED"
TIER_PROVEN = "PROVEN"

TIER_RANK: dict[str, int] = {
    TIER_INTUITED: 1,
    TIER_STRUCTURED: 2,
    TIER_MEASURED: 3,
    TIER_PROVEN: 4,
}

# Tiers allowed for default agent retrieval (INTUITED excluded)
RETRIEVAL_TIERS: frozenset[str] = frozenset(
    {TIER_STRUCTURED, TIER_MEASURED, TIER_PROVEN}
)

# ---------------------------------------------------------------------------
# Packet types
# ---------------------------------------------------------------------------

GOVERNED_PACKET_TYPES: frozenset[str] = frozenset(
    {"working_model", "decision", "method", "doctrine"}
)

ALL_PACKET_TYPES: frozenset[str] = frozenset(
    {
        "decision",
        "working_model",
        "method",
        "doctrine",
        "failure",
        "prompt_pattern",
        "reference",
        "conversation",
    }
)

# ---------------------------------------------------------------------------
# Route constants
# ---------------------------------------------------------------------------

ROUTE_KEEP = "keep"
ROUTE_FREEZE = "freeze"
ROUTE_REFINE = "refine"
ROUTE_QUARANTINE = "quarantine"
ROUTE_DROP_FROM_ACTIVE = "drop_from_active"
ROUTE_REVIEW = "review"
ROUTE_VALIDATE = "validate"

ACTIVE_ROUTES: frozenset[str] = frozenset({ROUTE_KEEP, ROUTE_FREEZE})

# ---------------------------------------------------------------------------
# Validation sample size
# ---------------------------------------------------------------------------

VALIDATION_SAMPLE_SIZE = 100
VALIDATION_MIN_ACTIVE = 10
VALIDATION_MIN_QUARANTINE = 10
VALIDATION_MIN_DUPLICATE = 10
VALIDATION_MIN_GEM = 10

# ---------------------------------------------------------------------------
# Secret / PII detection keywords (conservative)
# ---------------------------------------------------------------------------

SECRET_KEYWORDS: frozenset[str] = frozenset(
    {
        "api_key",
        "api-key",
        "apikey",
        "secret",
        "password",
        "passwd",
        "token",
        "bearer",
        "authorization",
        "private_key",
        "private-key",
        "ssh-rsa",
        "ssh-ed25519",
        "aws_access_key",
        "aws_secret_key",
    }
)

PII_KEYWORDS: frozenset[str] = frozenset(
    {
        "national insurance",
        "ni number",
        "date of birth",
        "passport number",
        "bank account",
        "sort code",
        "credit card",
        "ssn",
        "social security",
    }
)

# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

PIPELINE_PROVENANCE = "amplified-pipeline-v0.3"
