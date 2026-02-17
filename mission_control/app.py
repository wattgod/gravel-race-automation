"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from mission_control.config import STATIC_DIR
from mission_control.routers import (
    athletes, dashboard, pipeline, reports, templates_page, touchpoints, webhooks,
)
from mission_control.routers import sequences, deals_router, analytics, unsubscribe
from mission_control.routers import races_api

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Start the scheduler for sequence processing
    try:
        from mission_control.scheduler import scheduler
        scheduler.start()
        logger.info("Scheduler started — processing sequences every 15 minutes")
    except Exception as e:
        logger.warning("Scheduler failed to start: %s", e)

    yield

    # Shutdown
    try:
        from mission_control.scheduler import scheduler
        scheduler.shutdown(wait=False)
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="Gravel God Mission Control",
        description=(
            "Mission Control dashboard and the Gravel God Race Database API. "
            "Query 328 gravel and mountain bike races at /api/v1/races."
        ),
        version="1.0.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # Static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok"}

    # Routers — v1 (dashboard, internal — hidden from API docs)
    for r in [dashboard, athletes, pipeline, touchpoints, templates_page, reports, webhooks]:
        app.include_router(r.router, include_in_schema=False)

    # Routers — v2 (internal — hidden from API docs)
    for r in [sequences, deals_router, analytics, unsubscribe]:
        app.include_router(r.router, include_in_schema=False)

    # Races API — public, included in API docs
    app.include_router(races_api.router)

    return app
