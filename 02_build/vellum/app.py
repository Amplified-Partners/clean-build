"""Vellum — FastAPI application entrypoint.

Run with: uvicorn vellum.app:app --host 0.0.0.0 --port 8400
Or: python -m vellum.app

Scaffold (Devon-3397) | 2026-05-11
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from vellum.routes import router
from vellum.storage import init_store, get_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("vellum")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup/shutdown: init store, log config."""
    await init_store()
    db_url = os.environ.get("DATABASE_URL")
    backend = "PostgreSQL" if db_url else "in-memory"
    logger.info("Vellum started — storage: %s", backend)
    yield
    await get_store().close()
    logger.info("Vellum shut down")


app = FastAPI(
    title="Vellum",
    description="Shared sheet engine — Brief, Correspondence, Council.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "vellum"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("VELLUM_PORT", "8400"))
    uvicorn.run("vellum.app:app", host="0.0.0.0", port=port, reload=True)
