"""Brief mode routes — sheet read, reply, and entry listing.

All routes validate the share token. Invalid/expired token = 404 (no info leak).
HTML rendering for mobile view. JSON API for polling.

Devon-598da8fc | 2026-05-11
Refactored to storage layer + HTML render: Scaffold (Devon-3397) | 2026-05-11
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from vellum.render import render_brief
from vellum.webhooks.reply_to_loop import (
    SheetNotFoundError,
    TokenValidationError,
    get_sheet_from_store,
    process_reply,
    validate_token_async,
)

router = APIRouter(prefix="/api/v1/sheets", tags=["brief"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ReplyRequest(BaseModel):
    """Body for POST /reply."""

    content: str
    entry_type: Literal["emoji_reaction", "human_comment"]
    token: str


class EntryResponse(BaseModel):
    """Serialised sheet entry for JSON responses."""

    id: str
    sheet_id: str
    author: str
    content: str
    timestamp: str
    prev_hash: str
    entry_hash: str
    entry_type: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{sheet_id}")
async def render_brief_page(sheet_id: str, token: str = Query(...)) -> dict:
    """Render the brief sheet as JSON (API mode).

    Validates token from query param. Returns sheet data.
    """
    try:
        await validate_token_async(sheet_id, token, min_role="read")
    except TokenValidationError:
        raise HTTPException(status_code=404, detail="Not found")

    sheet = await get_sheet_from_store(sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail="Not found")

    entries = [
        EntryResponse(
            id=e.id,
            sheet_id=e.sheet_id,
            author=e.author,
            content=e.content,
            timestamp=e.timestamp.isoformat(),
            prev_hash=e.prev_hash,
            entry_hash=e.entry_hash,
            entry_type=e.entry_type,
        )
        for e in sheet.entries
    ]

    return {
        "sheet_id": sheet.meta.id,
        "title": sheet.meta.title,
        "tenant_id": sheet.meta.tenant_id,
        "entries": [e.model_dump() for e in entries],
    }


@router.get("/{sheet_id}/view", response_class=HTMLResponse)
async def render_brief_html(sheet_id: str, token: str = Query(...)) -> HTMLResponse:
    """Render the brief as a mobile-first HTML page.

    This is what Bob sees when he taps the iMessage link.
    """
    try:
        await validate_token_async(sheet_id, token, min_role="read")
    except TokenValidationError:
        raise HTTPException(status_code=404, detail="Not found")

    sheet = await get_sheet_from_store(sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail="Not found")

    # Build the template data from sheet entries
    headline_parts = []
    sections = []
    for entry in sheet.entries:
        if entry.entry_type == "agent_write":
            headline_parts.append(entry.content)
        elif entry.entry_type in ("emoji_reaction", "human_comment"):
            sections.append({
                "icon": entry.content if entry.entry_type == "emoji_reaction" else "💬",
                "title": f"Reply from {entry.author}",
                "summary": entry.content[:60],
                "details": entry.content,
            })

    now = datetime.utcnow()
    sheet_data = {
        "sheet_id": sheet.meta.id,
        "title": sheet.meta.title,
        "date": now.strftime("%A %d %B %Y"),
        "headline": " ".join(headline_parts) if headline_parts else "No data yet.",
        "sections": sections,
    }

    html = render_brief(sheet_data, token)
    return HTMLResponse(content=html)


@router.post("/{sheet_id}/reply")
async def accept_reply(sheet_id: str, body: ReplyRequest) -> dict:
    """Accept a reply (emoji or comment) from the reader."""
    try:
        entry = await process_reply(
            sheet_id=sheet_id,
            token=body.token,
            content=body.content,
            entry_type=body.entry_type,
        )
    except (SheetNotFoundError, TokenValidationError):
        raise HTTPException(status_code=404, detail="Not found")

    return {
        "status": "ok",
        "entry_id": entry.id,
        "entry_hash": entry.entry_hash,
    }


@router.get("/{sheet_id}/entries")
async def list_entries(sheet_id: str, token: str = Query(...)) -> dict:
    """JSON list of entries for polling/refresh."""
    try:
        await validate_token_async(sheet_id, token, min_role="read")
    except TokenValidationError:
        raise HTTPException(status_code=404, detail="Not found")

    sheet = await get_sheet_from_store(sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail="Not found")

    entries = [
        EntryResponse(
            id=e.id,
            sheet_id=e.sheet_id,
            author=e.author,
            content=e.content,
            timestamp=e.timestamp.isoformat(),
            prev_hash=e.prev_hash,
            entry_hash=e.entry_hash,
            entry_type=e.entry_type,
        )
        for e in sheet.entries
    ]

    return {
        "sheet_id": sheet.meta.id,
        "entries": [e.model_dump() for e in entries],
        "count": len(entries),
    }
