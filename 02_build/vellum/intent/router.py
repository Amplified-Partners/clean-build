"""Intent router — parses Ewan's text replies into actionable intents.

Emoji routing:
  👍 → acknowledge (log, no further action)
  ⚠️ → escalate (create urgent task)
  ❓ → clarify (trigger clarification agent)

Text routing (via keyword matching, upgradeable to LLM):
  "cancel/reschedule/move" → calendar_action
  "park/hold/pause" → park_task
  "do/fix/build/wire" → create_task
  "decide/decision/approved/go" → decision
  Fallback → general_reply

§3.3 fix (2026-05-20): confidence numbers replaced with honest
match_type and confidence_basis labels. The old 0.95/0.80/0.50
numbers were INTUITED designer judgement dressed as MEASURED
probabilities — the min-rule forbids this.

Devon-b5dc | 2026-05-14
Hardened by Dana | 2026-05-20 | §3.3 drop INTUITED-dressed-as-MEASURED confidence numbers
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

IntentKind = Literal[
    "acknowledge",
    "escalate",
    "clarify",
    "calendar_action",
    "park_task",
    "create_task",
    "decision",
    "general_reply",
]

MatchType = Literal["exact_emoji", "keyword", "fallback"]

EMOJI_MAP: dict[str, IntentKind] = {
    "👍": "acknowledge",
    "thumbsup": "acknowledge",
    "👌": "acknowledge",
    "✅": "acknowledge",
    "⚠️": "escalate",
    "warning": "escalate",
    "🔥": "escalate",
    "❓": "clarify",
    "question": "clarify",
}

KEYWORD_PATTERNS: list[tuple[re.Pattern[str], IntentKind]] = [
    (re.compile(r"\b(cancel|reschedule|move|postpone)\b", re.I), "calendar_action"),
    (re.compile(r"\b(park|hold|pause|defer|shelve)\b", re.I), "park_task"),
    (re.compile(r"\b(do|fix|build|wire|implement|ship|deploy)\b", re.I), "create_task"),
    (re.compile(r"\b(decide|decision|approved|go ahead|green.?light|confirmed)\b", re.I), "decision"),
]


@dataclass(frozen=True)
class Intent:
    """Classified intent from a human reply.

    match_type and confidence_basis replace the old numeric confidence
    field (§3.3). These are honest STRUCTURED labels — not INTUITED
    numbers pretending to be calibrated probabilities.
    """

    kind: IntentKind
    raw_content: str
    match_type: MatchType
    confidence_basis: str
    extracted_action: str


def classify_reply(content: str) -> Intent:
    """Classify a reply into an intent. Deterministic keyword matching."""
    stripped = content.strip()

    if stripped in EMOJI_MAP:
        return Intent(
            kind=EMOJI_MAP[stripped],
            raw_content=content,
            match_type="exact_emoji",
            confidence_basis="exact emoji match — deterministic",
            extracted_action=stripped,
        )

    for pattern, intent_kind in KEYWORD_PATTERNS:
        match = pattern.search(stripped)
        if match:
            return Intent(
                kind=intent_kind,
                raw_content=content,
                match_type="keyword",
                confidence_basis="keyword pattern match — deterministic, designer-selected patterns",
                extracted_action=match.group(0),
            )

    return Intent(
        kind="general_reply",
        raw_content=content,
        match_type="fallback",
        confidence_basis="no pattern matched — fallback classification",
        extracted_action=stripped,
    )
