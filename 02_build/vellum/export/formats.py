# Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f)
"""Canonical JSON serialization for deterministic signing.

Canonical form: sorted keys, no whitespace padding, UTF-8 encoding.
This ensures that the same data always produces the same byte sequence,
which is required for signature verification.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(data: Any) -> bytes:
    """Serialize data to canonical JSON bytes.

    Rules:
    - Keys sorted recursively
    - Compact separators: (',', ':')
    - UTF-8 encoding
    - No trailing newline
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_json_str(data: Any) -> str:
    """Serialize data to canonical JSON string."""
    return canonical_json(data).decode("utf-8")


def content_hash(data: Any) -> str:
    """Compute SHA-256 hash of canonical JSON representation."""
    return hashlib.sha256(canonical_json(data)).hexdigest()
