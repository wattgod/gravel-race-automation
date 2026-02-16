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
