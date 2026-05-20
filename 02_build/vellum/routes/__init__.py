"""Vellum routes.

Dana | 2026-05-20 | Added correspondence router
"""

from fastapi import APIRouter

from vellum.routes.brief import router as brief_router
from vellum.routes.correspondence import router as correspondence_router
from vellum.routes.council import router as council_router
from vellum.routes.reply import router as reply_router
from vellum.routes.ui import router as ui_router

router = APIRouter()
router.include_router(brief_router)
router.include_router(correspondence_router)
router.include_router(council_router)
router.include_router(reply_router)
router.include_router(ui_router)
