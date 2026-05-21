"""Vellum — contact surface application.

FastAPI app serving:
- REST API for sheets, entries, replies, decisions, read receipts
- Simple HTMX-powered UI for Ewan
- Scheduled morning/evening brief generation

Auth Ulysses boot check (§3.2): refuses to start without auth
unless explicitly in dev mode. Production deployments set
VELLUM_REQUIRE_AUTH=1 which overrides dev mode entirely.

Devon-b5dc | 2026-05-14 | session <id>
Hardened by Dana | 2026-05-20 | §3.2 auth Ulysses boot check
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from vellum.canvas.mode_guard import ModeViolationError
from vellum.cron.briefs import generate_morning_brief
from vellum.routes import router
from vellum.storage import init_store

log = logging.getLogger("vellum")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

VELLUM_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# §3.2 — Auth Ulysses boot check
# ---------------------------------------------------------------------------


def _check_auth_config() -> None:
    """Refuse to start without auth unless explicitly in dev mode.

    Two-flag safety:
    - VELLUM_REQUIRE_AUTH=1 → auth MUST be enabled. Ignores dev mode.
    - VELLUM_AUTH_ENABLED=0 (or unset) without VELLUM_DEV_MODE=1 → refuse.

    This is a Ulysses commitment in the boot path. One env-var slip
    does not silently disable auth in production.
    """
    require_auth = os.environ.get("VELLUM_REQUIRE_AUTH", "")
    auth_enabled = os.environ.get("VELLUM_AUTH_ENABLED", "")
    dev_mode = os.environ.get("VELLUM_DEV_MODE", "")

    if require_auth == "1":
        if auth_enabled != "1":
            raise SystemExit(
                "VELLUM_REQUIRE_AUTH=1 but VELLUM_AUTH_ENABLED!=1; "
                "refusing to start. This is a Ulysses clause — auth "
                "cannot be bypassed when VELLUM_REQUIRE_AUTH is set."
            )
        log.info("Auth config: REQUIRE_AUTH=1, AUTH_ENABLED=1 — production mode")
        return

    if auth_enabled != "1" and dev_mode != "1":
        raise SystemExit(
            "Auth disabled outside dev mode; refusing to start. "
            "Set VELLUM_DEV_MODE=1 for development or "
            "VELLUM_AUTH_ENABLED=1 for production."
        )

    if dev_mode == "1":
        log.warning("Auth config: DEV_MODE=1 — auth enforcement relaxed")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _check_auth_config()

    store = await init_store()
    log.info("Vellum store initialised")

    if os.environ.get("VELLUM_DEV_MODE", "0") == "1":
        log.info("DEV MODE: generating demo morning brief")
        sheet_id = await generate_morning_brief()
        log.info("DEV MODE: demo brief created: %s", sheet_id)

    yield

    await store.close()
    log.info("Vellum store closed")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


app = FastAPI(
    title="Vellum",
    description="Contact surface for Ewan and agents — Amplified Partners",
    version="0.2.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Global exception handler for ModeViolationError (§2.3)
# ---------------------------------------------------------------------------


@app.exception_handler(ModeViolationError)
async def mode_violation_handler(request: Request, exc: ModeViolationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc),
            "error_type": "mode_violation",
            "mode": exc.mode,
            "entry_type": exc.entry_type,
        },
    )


_STATIC_DIR = VELLUM_DIR / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
app.include_router(router)
