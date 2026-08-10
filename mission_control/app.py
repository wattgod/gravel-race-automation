"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from mission_control.config import STATIC_DIR
from mission_control.middleware.auth import require_admin
from mission_control.routers import (
    athletes, dashboard, pipeline, reports, templates_page, touchpoints, triage, webhooks,
)
from mission_control.routers import sequences, deals_router, analytics, unsubscribe
from mission_control.routers import races_api, nutrition_api
from mission_control.routers import auth_routes

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

    # Startup probe: record whether race-dates fetches work from THIS
    # environment. The countdown job aborted silently for weeks because the
    # fetch failed only in prod — this writes the pass/fail (with the actual
    # exception) to gg_audit_log on every deploy.
    try:
        import asyncio as _asyncio
        from mission_control import supabase_client as _db
        from mission_control.services.race_countdown import probe_race_dates

        async def _startup_probe():
            try:
                detail = await _asyncio.to_thread(probe_race_dates)
                _db.log_action("race_dates_probe", "system", "startup", detail[:500])
                logger.info("race-dates startup probe: %s", detail)
            except Exception as e:
                logger.warning("race-dates startup probe failed: %s", e)

        _asyncio.get_running_loop().create_task(_startup_probe())
    except Exception as e:
        logger.warning("race-dates startup probe not scheduled: %s", e)

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

    # Routers — admin-protected (dashboard, internal — hidden from API docs)
    _admin = [Depends(require_admin)]
    for r in [dashboard, triage, athletes, pipeline, touchpoints, templates_page, reports]:
        app.include_router(r.router, include_in_schema=False, dependencies=_admin)

    # Auth routes — public (login/logout pages)
    app.include_router(auth_routes.router, include_in_schema=False)

    # Webhooks have their own WEBHOOK_SECRET auth — no admin dependency
    app.include_router(webhooks.router, include_in_schema=False)

    # Routers — v2 admin-protected (internal — hidden from API docs)
    for r in [sequences, deals_router, analytics]:
        app.include_router(r.router, include_in_schema=False, dependencies=_admin)

    # Unsubscribe — public, no auth (CAN-SPAM compliance)
    app.include_router(unsubscribe.router, include_in_schema=False)

    # Races API — public, included in API docs
    app.include_router(races_api.router)

    # Nutrition API — public, included in API docs
    app.include_router(nutrition_api.router)

    return app
