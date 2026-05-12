"""Internal webhook route — brief generation trigger.

POST /api/v1/internal/brief/generate
Used by cron or manual trigger to kick off brief generation for a tenant.

Devon-598da8fc | 2026-05-11
Refactored to storage layer: Scaffold (Devon-3397) | 2026-05-11
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from vellum.models.entry import SheetEntry
from vellum.models.sheet import Sheet, SheetMeta
from vellum.models.token import ShareToken
from vellum.storage import get_store
from vellum.webhooks.reply_to_loop import register_sheet, register_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/internal/brief", tags=["internal"])


class GenerateRequest(BaseModel):
    """Body for POST /generate."""

    tenant_id: str


class GenerateResponse(BaseModel):
    """Response for brief generation."""

    status: str
    sheet_id: str
    tenant_id: str
    entry_count: int
    token_id: str = ""
    view_url: str = ""


@router.post("/generate")
async def generate_brief(body: GenerateRequest) -> GenerateResponse:
    """Trigger brief generation for a tenant.

    Creates a sheet with a placeholder entry and a read token.
    Returns the sheet_id and token for viewing.
    """
    now = datetime.now(timezone.utc)
    meta = SheetMeta(
        tenant_id=body.tenant_id,
        title=f"Daily Brief — {now.strftime('%A %d %B %Y')}",
        mode="brief",
        created_by="vellum-generator",
    )

    entry = SheetEntry(
        sheet_id=meta.id,
        author="vellum-generator",
        content="Good morning! Here is your daily brief.",
        entry_type="agent_write",
    )

    # Create a read token for viewing
    token = ShareToken(
        sheet_id=meta.id,
        role="comment",
        expires_at=now + timedelta(hours=72),
    )

    sheet = Sheet(
        meta=meta,
        entries=[entry],
        latest_hash=entry.entry_hash,
    )

    # Try storage layer, fall back to in-memory
    try:
        store = get_store()
        await store.create_sheet(body.tenant_id, meta)
        await store.append_entry(meta.id, entry)
        await store.store_token(token)
    except RuntimeError:
        register_sheet(sheet)
        register_token(token)

    # Always register in legacy store for test compat
    register_sheet(sheet)
    register_token(token)

    logger.info(
        "Generated brief sheet=%s tenant=%s token=%s",
        meta.id,
        body.tenant_id,
        token.token_id,
    )

    return GenerateResponse(
        status="ok",
        sheet_id=meta.id,
        tenant_id=body.tenant_id,
        entry_count=1,
        token_id=token.token_id,
        view_url=f"/api/v1/sheets/{meta.id}/view?token={token.token_id}",
    )
