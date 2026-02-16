"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from mission_control.config import STATIC_DIR
from mission_control.routers import (
    athletes, dashboard, pipeline, reports, templates_page, touchpoints, webhooks,
)


def create_app() -> FastAPI:
    app = FastAPI(title="Gravel God Mission Control", docs_url=None, redoc_url=None)

    # Static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Routers
    app.include_router(dashboard.router)
    app.include_router(athletes.router)
    app.include_router(pipeline.router)
    app.include_router(touchpoints.router)
    app.include_router(templates_page.router)
    app.include_router(reports.router)
    app.include_router(webhooks.router)

    return app
