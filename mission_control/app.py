"""FastAPI application factory."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from mission_control.config import STATIC_DIR
from mission_control.middleware.auth import require_admin
from mission_control.routers import dashboard, templates_page, triage, webhooks
from mission_control.routers import sequences, deals_router, analytics, unsubscribe
from mission_control.routers import races_api, nutrition_api
from mission_control.routers import auth_routes
from mission_control.routers import lead_replies

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# At INFO these libraries log every request URL, and database lookups put
# customer email addresses in the URL. Keep them at WARNING.
_QUIET_LOGGERS = ("httpx", "httpcore", "hpack", "postgrest")


def configure_logging() -> None:
    """Root logger at INFO so the app's own lines reach Railway logs."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger().setLevel(logging.INFO)
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

# Present (set and non-empty) by name. Values are never read out or returned.
REQUIRED_SETTINGS = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "RESEND_API_KEY",
    "WEBHOOK_SECRET",
    "MISSION_CONTROL_SECRET",
)

JOBS_STALE_AFTER = timedelta(minutes=45)
FIRST_START_WINDOW = timedelta(hours=2)
# gg_settings key holding the previous server start time, so a crash loop
# (a restart every few minutes, no tick ever completing) cannot stay green on
# the start-up grace period.
LAST_START_SETTING = "mc_last_start_utc"

# In-memory job health for this process. Lives here, not in scheduler.py, so
# tests that stub the scheduler module do not replace it.
_job_health: dict = {
    "started": None,          # datetime this process started
    "first_start": False,     # no other start in the previous FIRST_START_WINDOW
    "last_good_tick": None,   # datetime of the last good process_sequences run
    "last_run": None,         # {processed, sent, errors} of the last run
}


def record_sequence_tick(result: dict) -> None:
    """Record a process_sequences run. Good = not skipped, and not every send failed."""
    processed = int(result.get("processed", 0) or 0)
    sent = int(result.get("sent", 0) or 0)
    _job_health["last_run"] = {
        "processed": processed,
        "sent": sent,
        "errors": int(result.get("errors", 0) or 0),
    }
    if not result.get("skipped") and (processed == 0 or sent > 0):
        _job_health["last_good_tick"] = datetime.now(timezone.utc)


def record_server_start(now: datetime | None = None) -> bool:
    """Store this start in gg_settings; return True if no other start happened
    in the previous FIRST_START_WINDOW. A database failure counts as "not the
    first start" so the grace period is never granted on doubt."""
    from mission_control import supabase_client as db

    now = now or datetime.now(timezone.utc)
    first = False
    try:
        previous = db.get_setting(LAST_START_SETTING, "")
        if previous:
            prev_dt = datetime.fromisoformat(previous)
            first = now - prev_dt >= FIRST_START_WINDOW
        else:
            first = True
    except Exception as e:
        logger.warning("Could not read last server start: %s", e)
        first = False
    try:
        db.set_setting(LAST_START_SETTING, now.isoformat())
    except Exception as e:
        logger.warning("Could not record server start: %s", e)
        first = False
    _job_health["first_start"] = first
    return first


def _scheduler_running() -> bool:
    try:
        from mission_control.scheduler import scheduler
        return scheduler.running is True
    except Exception:
        return False


def _missing_settings() -> list[str]:
    return [name for name in REQUIRED_SETTINGS if not os.environ.get(name, "").strip()]


def health_problems() -> list[str]:
    """Names of failed checks — never values."""
    problems = []
    if not _scheduler_running():
        problems.append("scheduler not running")
    problems.extend(f"missing setting: {name}" for name in _missing_settings())
    return problems


def jobs_health(now: datetime | None = None) -> dict:
    """Body for /health/jobs: counts and times only, never addresses."""
    now = now or datetime.now(timezone.utc)
    last_good = _job_health["last_good_tick"]
    started = _job_health["started"]
    fresh_tick = last_good is not None and now - last_good < JOBS_STALE_AFTER
    in_grace = (
        started is not None
        and now - started < JOBS_STALE_AFTER
        and bool(_job_health["first_start"])
    )
    return {
        "last_good_tick_utc": last_good.isoformat() if last_good else None,
        "started_utc": started.isoformat() if started else None,
        "last_run": _job_health["last_run"],
        "ok": bool(fresh_tick or in_grace),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Start the scheduler for sequence processing. A failure here makes
    # /health answer 503, so Railway refuses the deploy and keeps the old one.
    try:
        from mission_control.scheduler import scheduler
        scheduler.start()
        logger.info("Scheduler started — processing sequences every 15 minutes")
    except Exception as e:
        logger.error("Scheduler failed to start: %s", e)

    _job_health["started"] = datetime.now(timezone.utc)
    _job_health["first_start"] = False
    _job_health["last_good_tick"] = None
    _job_health["last_run"] = None
    try:
        import asyncio as _asyncio

        async def _record_start():
            try:
                await _asyncio.to_thread(record_server_start)
            except Exception as e:
                logger.warning("server start not recorded: %s", e)

        _asyncio.get_running_loop().create_task(_record_start())
    except Exception as e:
        logger.warning("server start recording not scheduled: %s", e)

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
                # room for all three brands' failure detail (status,
                # content type, body start); details is a TEXT column
                _db.log_action("race_dates_probe", "system", "startup", detail[:1500])
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
        # Railway's deploy health check: 503 keeps the previous deploy live.
        problems = health_problems()
        if problems:
            # Names go to the log, not the public body: they would tell anyone
            # which protection is off.
            logger.error("health check failed: %s", "; ".join(problems))
            return JSONResponse({"status": "unhealthy"}, status_code=503)
        return {"status": "ok"}

    @app.get("/health/jobs", include_in_schema=False)
    async def health_jobs():
        # Polled hourly by .github/workflows/mission-control-heartbeat.yml.
        body = jobs_health()
        return JSONResponse(body, status_code=200 if body["ok"] else 503)

    # Routers — admin-protected (dashboard, internal — hidden from API docs)
    _admin = [Depends(require_admin)]
    for r in [dashboard, triage, templates_page]:
        app.include_router(r.router, include_in_schema=False, dependencies=_admin)

    # Auth routes — public (login/logout pages)
    app.include_router(auth_routes.router, include_in_schema=False)

    # Webhooks have their own WEBHOOK_SECRET auth — no admin dependency
    app.include_router(webhooks.router, include_in_schema=False)

    # Routers — v2 admin-protected (internal — hidden from API docs)
    for r in [sequences, deals_router, analytics, lead_replies]:
        app.include_router(r.router, include_in_schema=False, dependencies=_admin)

    # Unsubscribe — public, no auth (CAN-SPAM compliance)
    app.include_router(unsubscribe.router, include_in_schema=False)

    # Public, unauthenticated: the 2027 goal poster, served from the lead's
    # own unguessable token (docs/specs/goals-2027-funnel-spec.md D8).
    from mission_control.routers import poster

    app.include_router(poster.router, include_in_schema=False)

    # Public, unauthenticated: /season-plan/'s read-only prefill from the
    # same poster_token (D9) — name/email/goal/A-race/habits only.
    from mission_control.routers import season_plan_prefill

    app.include_router(season_plan_prefill.router, include_in_schema=False)

    # Races API — public, included in API docs
    app.include_router(races_api.router)

    # Nutrition API — public, included in API docs
    app.include_router(nutrition_api.router)

    return app
