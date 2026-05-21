"""Dashboard API — Mission Control integration.

Single-call governance snapshot for the Mission Control dashboard.
Returns everything the UI needs: active conversations, recent
decisions, agent activity, epistemic tier health, unread items,
and council verdicts.

Mission Control is the governance UI (present state).
Vellum is the witness ledger (past state).
DuckDB is the analytics engine (the math).
This route is the bridge between them.

Dana | 2026-05-20 | Mission Control integration
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter

from vellum.models.entry import SheetEntry
from vellum.routes.correspondence import _get_participants
from vellum.storage import get_store

log = logging.getLogger("vellum.dashboard")
router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry_summary(entry: SheetEntry) -> dict:
    """Compact entry representation for the dashboard."""
    return {
        "id": entry.id,
        "author": entry.author,
        "content": entry.content[:200] + ("..." if len(entry.content) > 200 else ""),
        "entry_type": entry.entry_type,
        "epistemic_tier": entry.epistemic_tier,
        "timestamp": entry.timestamp.isoformat(),
        "entry_hash": entry.entry_hash,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/snapshot")
async def governance_snapshot(tenant_id: str = "ewan") -> dict:
    """Full governance snapshot for Mission Control.

    Returns everything the dashboard needs in one call:
    - Active conversations with participant lists
    - Recent decisions (last 20)
    - Agent activity summary
    - Epistemic tier distribution
    - Unread items
    - Mode breakdown
    - Council escalations
    """
    store = get_store()
    sheets = await store.list_sheets(tenant_id)

    # Collect all entries across sheets
    all_entries: list[tuple[SheetEntry, str]] = []  # (entry, mode)
    for sheet in sheets:
        for entry in sheet.entries:
            all_entries.append((entry, sheet.meta.mode))

    # Sort by timestamp descending
    all_entries.sort(key=lambda x: x[0].timestamp, reverse=True)

    # --- Active conversations ---
    conversations = []
    for sheet in sheets:
        if sheet.meta.mode == "correspondence":
            participants = _get_participants(sheet.meta.id)
            conversations.append({
                "sheet_id": sheet.meta.id,
                "title": sheet.meta.title,
                "participant_count": len(participants),
                "participants": [p.identity for p in participants if p.active],
                "message_count": len(sheet.entries),
                "last_message": sheet.entries[-1].timestamp.isoformat() if sheet.entries else None,
                "last_author": sheet.entries[-1].author if sheet.entries else None,
            })

    # --- Recent decisions ---
    decisions = [
        _entry_summary(e)
        for e, mode in all_entries
        if e.entry_type == "decision"
    ][:20]

    # --- Agent activity ---
    agent_stats: dict[str, dict] = defaultdict(lambda: {
        "entries": 0, "conversations": set(), "last_seen": None,
        "tiers": defaultdict(int),
    })
    for entry, mode in all_entries:
        stats = agent_stats[entry.author]
        stats["entries"] += 1
        stats["conversations"].add(entry.sheet_id)
        stats["tiers"][entry.epistemic_tier] += 1
        if stats["last_seen"] is None:
            stats["last_seen"] = entry.timestamp

    agents = [
        {
            "identity": author,
            "entries": stats["entries"],
            "conversations": len(stats["conversations"]),
            "last_seen": stats["last_seen"].isoformat() if stats["last_seen"] else None,
            "tier_breakdown": dict(stats["tiers"]),
        }
        for author, stats in sorted(
            agent_stats.items(),
            key=lambda x: x[1]["entries"],
            reverse=True,
        )
    ]

    # --- Epistemic tier distribution ---
    tier_counts: dict[str, int] = defaultdict(int)
    for entry, mode in all_entries:
        tier_counts[entry.epistemic_tier] += 1
    total = sum(tier_counts.values()) or 1
    tier_distribution = {
        tier: {"count": count, "pct": round(count * 100 / total, 1)}
        for tier, count in sorted(tier_counts.items())
    }

    # --- Mode breakdown ---
    mode_counts: dict[str, int] = defaultdict(int)
    mode_sheets: dict[str, int] = defaultdict(int)
    for sheet in sheets:
        mode_sheets[sheet.meta.mode] += 1
        mode_counts[sheet.meta.mode] += len(sheet.entries)
    modes = {
        mode: {"sheets": mode_sheets[mode], "entries": mode_counts[mode]}
        for mode in sorted(set(list(mode_sheets.keys()) + list(mode_counts.keys())))
    }

    # --- Unread items ---
    unread = await store.get_unread(tenant_id)

    # --- Council escalations ---
    escalations = [
        _entry_summary(e)
        for e, mode in all_entries
        if e.metadata.get("escalate") is True
        or e.metadata.get("requires_human_followup") is True
    ][:10]

    return {
        "tenant_id": tenant_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_sheets": len(sheets),
            "total_entries": len(all_entries),
            "active_conversations": len(conversations),
            "pending_decisions": len([d for d in decisions if True]),
            "unread_count": len(unread),
            "escalation_count": len(escalations),
        },
        "conversations": conversations,
        "recent_decisions": decisions,
        "agents": agents,
        "tier_distribution": tier_distribution,
        "modes": modes,
        "unread": [_entry_summary(e) for e in unread[:10]],
        "escalations": escalations,
    }


@router.get("/conversations")
async def list_conversations(tenant_id: str = "ewan") -> dict:
    """List all correspondence conversations with metadata."""
    store = get_store()
    sheets = await store.list_sheets(tenant_id)

    conversations = []
    for sheet in sheets:
        if sheet.meta.mode != "correspondence":
            continue
        participants = _get_participants(sheet.meta.id)
        conversations.append({
            "sheet_id": sheet.meta.id,
            "title": sheet.meta.title,
            "created_at": sheet.meta.created_at.isoformat(),
            "created_by": sheet.meta.created_by,
            "participant_count": len(participants),
            "participants": [
                {
                    "identity": p.identity,
                    "type": p.participant_type,
                    "role": p.role,
                    "max_tier": p.max_tier,
                }
                for p in participants
            ],
            "message_count": len(sheet.entries),
            "last_message": sheet.entries[-1].timestamp.isoformat() if sheet.entries else None,
        })

    return {"conversations": conversations, "count": len(conversations)}


@router.get("/agents")
async def agent_roster(tenant_id: str = "ewan") -> dict:
    """Agent fleet status — who's active, what they're doing, tier compliance."""
    store = get_store()
    sheets = await store.list_sheets(tenant_id)

    agent_data: dict[str, dict] = defaultdict(lambda: {
        "entries": 0, "sheets": set(), "modes": set(),
        "tiers": defaultdict(int), "entry_types": defaultdict(int),
        "first_seen": None, "last_seen": None,
    })

    for sheet in sheets:
        for entry in sheet.entries:
            a = agent_data[entry.author]
            a["entries"] += 1
            a["sheets"].add(entry.sheet_id)
            a["modes"].add(sheet.meta.mode)
            a["tiers"][entry.epistemic_tier] += 1
            a["entry_types"][entry.entry_type] += 1
            if a["first_seen"] is None or entry.timestamp < a["first_seen"]:
                a["first_seen"] = entry.timestamp
            if a["last_seen"] is None or entry.timestamp > a["last_seen"]:
                a["last_seen"] = entry.timestamp

    agents = []
    for identity, data in sorted(agent_data.items(), key=lambda x: x[1]["entries"], reverse=True):
        agents.append({
            "identity": identity,
            "entries": data["entries"],
            "sheets": len(data["sheets"]),
            "modes": sorted(data["modes"]),
            "tier_breakdown": dict(data["tiers"]),
            "entry_types": dict(data["entry_types"]),
            "first_seen": data["first_seen"].isoformat() if data["first_seen"] else None,
            "last_seen": data["last_seen"].isoformat() if data["last_seen"] else None,
        })

    return {"agents": agents, "count": len(agents)}


@router.get("/health")
async def system_health(tenant_id: str = "ewan") -> dict:
    """System health indicators for Mission Control.

    Checks:
    - Epistemic tier compliance (is the min-rule being respected?)
    - Hash chain integrity across sheets
    - Conversation activity (any stale sheets?)
    - Agent diversity (are multiple agents active?)
    """
    from vellum.canvas.hash_chain import HashChain

    store = get_store()
    sheets = await store.list_sheets(tenant_id)

    chain_valid = 0
    chain_invalid = 0
    for sheet in sheets:
        if sheet.entries and HashChain.validate_chain(sheet.entries):
            chain_valid += 1
        elif sheet.entries:
            chain_invalid += 1

    # Tier compliance: count any entries where metadata shows tier was capped
    tier_caps = 0
    total_entries = 0
    for sheet in sheets:
        for entry in sheet.entries:
            total_entries += 1
            if entry.metadata.get("tier_capped"):
                tier_caps += 1

    # Active agents (last 24h)
    now = datetime.now(timezone.utc)
    recent_authors = set()
    for sheet in sheets:
        for entry in sheet.entries:
            age_hours = (now - entry.timestamp).total_seconds() / 3600
            if age_hours <= 24:
                recent_authors.add(entry.author)

    return {
        "status": "healthy" if chain_invalid == 0 else "degraded",
        "chain_integrity": {
            "valid": chain_valid,
            "invalid": chain_invalid,
            "total": chain_valid + chain_invalid,
        },
        "epistemic_compliance": {
            "tier_caps_applied": tier_caps,
            "total_entries": total_entries,
            "cap_rate_pct": round(tier_caps * 100 / total_entries, 1) if total_entries else 0,
        },
        "activity": {
            "total_sheets": len(sheets),
            "total_entries": total_entries,
            "active_agents_24h": len(recent_authors),
            "active_agent_list": sorted(recent_authors),
        },
    }
