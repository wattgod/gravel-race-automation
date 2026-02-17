"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from mission_control.config import STATIC_DIR
from mission_control.routers import (
    athletes, dashboard, pipeline, reports, templates_page, touchpoints, webhooks,
)
from mission_control.routers import sequences, deals_router, analytics

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
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Routers — v1
    app.include_router(dashboard.router)
    app.include_router(athletes.router)
    app.include_router(pipeline.router)
    app.include_router(touchpoints.router)
    app.include_router(templates_page.router)
    app.include_router(reports.router)
    app.include_router(webhooks.router)

    # Routers — v2
    app.include_router(sequences.router)
    app.include_router(deals_router.router)
    app.include_router(analytics.router)

    return app
