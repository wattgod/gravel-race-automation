"""APScheduler — runs sequence processing every 15 minutes, plus the daily jobs."""

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from mission_control import supabase_client as db

from mission_control.services.sequence_engine import process_due_sends

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@scheduler.scheduled_job("interval", minutes=15, id="process_sequences")
async def process_sequences():
    """Process due sequence sends every 15 minutes."""
    try:
        result = await process_due_sends()
        from mission_control.app import record_sequence_tick
        record_sequence_tick(result)
        if result["processed"] > 0:
            logger.info(
                "Sequence processing: %d processed, %d sent, %d errors",
                result["processed"],
                result["sent"],
                result["errors"],
            )
    except Exception as e:
        logger.error("Sequence processing failed: %s", e)


# ---------------------------------------------------------------------------
# Daily jobs: three chances a day, at most one run a day
# ---------------------------------------------------------------------------
#
# Each daily job has three slots (its usual time, +3 h, +6 h) so a restart at
# the wrong minute cannot lose the day. Every cap in these jobs is per run, so
# running three times would triple daily volume: a run first looks for a
# daily_job_done row in gg_audit_log for '<job>:<UTC date>' and returns at once
# if one exists. The row is written only when the run returned without raising
# and without flagging summary["aborted"], so an aborted run (race data fetch
# failed, too many errors) leaves the next slot to retry.
#
# The check-then-run is not atomic: two containers alive together during a
# deploy (about a minute) could both pass the check in the same slot. Accepted.

DAILY_JOB_DONE = "daily_job_done"


def _daily_marker_id(job: str, day) -> str:
    return f"{job}:{day.isoformat()}"


def _daily_job_done(job: str, day) -> bool:
    rows = db.select(
        "gg_audit_log", columns="id",
        match={"action": DAILY_JOB_DONE, "entity_id": _daily_marker_id(job, day)},
        limit=1,
    )
    return bool(rows)


async def _run_daily(job: str, runner) -> bool:
    """Run *runner* once per UTC day. Returns True when it ran to completion now."""
    today = datetime.now(timezone.utc).date()
    try:
        if await asyncio.to_thread(_daily_job_done, job, today):
            return False
    except Exception as e:
        # Cannot tell whether today's run happened: do not risk a second one.
        # The next slot checks again.
        logger.error("%s: could not read the done-today marker, skipping this slot: %s", job, e)
        return False

    try:
        result = await runner()
    except Exception as e:
        logger.error("%s failed: %s", job, e)
        return False

    if isinstance(result, dict) and result.get("aborted"):
        logger.warning("%s aborted; a later slot today will retry", job)
        return False

    try:
        await asyncio.to_thread(
            db.log_action, DAILY_JOB_DONE, "scheduler", _daily_marker_id(job, today), "",
        )
    except Exception as e:
        logger.error("%s: could not write the done-today marker: %s", job, e)
    return True


@scheduler.scheduled_job("cron", hour="14,17,20", id="race_countdown")
async def race_countdown():
    """Daily weeks-to-race countdown enrollment (14:00 UTC; retries 17:00, 20:00)."""
    from mission_control.services.race_countdown import run_race_countdown
    await _run_daily("race_countdown", run_race_countdown)


@scheduler.scheduled_job("cron", hour="14,17,20", minute=30, id="race_debrief")
async def race_debrief():
    """Daily post-race debrief enrollment (14:30 UTC, after countdown; retries 17:30, 20:30)."""
    from mission_control.services.race_debrief import run_race_debrief
    await _run_daily("race_debrief", run_race_debrief)


@scheduler.scheduled_job("cron", hour="15,18,21", id="race_watch")
async def race_watch():
    """Daily race-entry change notifications (15:00 UTC; retries 18:00, 21:00)."""
    from mission_control.services.race_watch import run_race_watch
    await _run_daily("race_watch", run_race_watch)


@scheduler.scheduled_job("cron", hour="15,18,21", minute=30, id="win_back")
async def win_back():
    """Daily cold-lead win-back enrollment (15:30 UTC, after the debrief and
    race-watch jobs; retries 18:30, 21:30). A no-op unless WIN_BACK_ENABLED is
    set; capped per run by WIN_BACK_DAILY_CAP. The 15-minute process_sequences
    job sends."""
    from mission_control.services.win_back import run_win_back
    await _run_daily("win_back", run_win_back)
