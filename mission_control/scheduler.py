"""APScheduler — runs sequence processing every 15 minutes."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from mission_control.services.sequence_engine import process_due_sends

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@scheduler.scheduled_job("interval", minutes=15, id="process_sequences")
async def process_sequences():
    """Process due sequence sends every 15 minutes."""
    try:
        result = await process_due_sends()
        if result["processed"] > 0:
            logger.info(
                "Sequence processing: %d processed, %d sent, %d errors",
                result["processed"],
                result["sent"],
                result["errors"],
            )
    except Exception as e:
        logger.error("Sequence processing failed: %s", e)


@scheduler.scheduled_job("cron", hour=14, id="race_countdown")
async def race_countdown():
    """Daily weeks-to-race countdown enrollment (14:00 UTC)."""
    from mission_control.services.race_countdown import run_race_countdown
    try:
        await run_race_countdown()
    except Exception as e:
        logger.error("Race countdown failed: %s", e)


@scheduler.scheduled_job("cron", hour=14, minute=30, id="race_debrief")
async def race_debrief():
    """Daily post-race debrief enrollment (14:30 UTC, after countdown)."""
    from mission_control.services.race_debrief import run_race_debrief
    try:
        await run_race_debrief()
    except Exception as e:
        logger.error("Race debrief failed: %s", e)
