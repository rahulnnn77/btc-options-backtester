"""
scheduler.py — APScheduler integration for automated strategy execution.
Strategies fire on a cron schedule, enter paper trades automatically.
"""
import json
import logging
from datetime import datetime
from typing import Optional, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("scheduler")

# Global scheduler instance (created once on app startup)
scheduler: Optional[AsyncIOScheduler] = None

# Callback set by main.py to fire a paper trade on schedule
_fire_callback: Optional[Callable] = None


def init_scheduler(fire_callback: Callable) -> AsyncIOScheduler:
    """
    Initialise and start the APScheduler.
    fire_callback(job_id, strategy, params) is called when a job fires.
    """
    global scheduler, _fire_callback
    _fire_callback = fire_callback

    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    scheduler.start()
    logger.info("✅ APScheduler started (timezone: Asia/Kolkata)")
    return scheduler


def add_job(job_id: int, cron_expr: str, strategy: list, params: dict):
    """Add or replace a scheduled job by DB id."""
    if scheduler is None:
        raise RuntimeError("Scheduler not initialised.")

    # Parse 5-field cron: "min hour dom mon dow"
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: '{cron_expr}'. Expected 5 fields.")

    minute, hour, day, month, dow = parts
    trigger = CronTrigger(
        minute=minute, hour=hour, day=day,
        month=month, day_of_week=dow,
        timezone="Asia/Kolkata",
    )

    scheduler.add_job(
        func       = _job_wrapper,
        trigger    = trigger,
        id         = f"job_{job_id}",
        name       = f"Strategy Job #{job_id}",
        args       = [job_id, strategy, params],
        replace_existing = True,
        max_instances    = 1,
        misfire_grace_time = 3600,  # allow up to 1h late
    )
    logger.info(f"  Scheduled job #{job_id} with cron '{cron_expr}'")


def pause_job(job_id: int):
    if scheduler:
        scheduler.pause_job(f"job_{job_id}")
        logger.info(f"  Paused job #{job_id}")


def resume_job(job_id: int):
    if scheduler:
        scheduler.resume_job(f"job_{job_id}")
        logger.info(f"  Resumed job #{job_id}")


def remove_job(job_id: int):
    if scheduler:
        try:
            scheduler.remove_job(f"job_{job_id}")
            logger.info(f"  Removed job #{job_id}")
        except Exception:
            pass


def get_next_run(job_id: int) -> Optional[str]:
    """Return ISO timestamp of next scheduled run, or None."""
    if scheduler is None:
        return None
    job = scheduler.get_job(f"job_{job_id}")
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None


async def _job_wrapper(job_id: int, strategy: list, params: dict):
    """Async wrapper that calls the registered fire_callback."""
    logger.info(f"⏰ Scheduled job #{job_id} fired at {datetime.now().isoformat()}")
    if _fire_callback:
        try:
            await _fire_callback(job_id, strategy, params)
        except Exception as e:
            logger.error(f"  Job #{job_id} failed: {e}")
