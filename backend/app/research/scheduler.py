import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import ResearchScheduleModel

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def trigger_scheduled_run(schedule_id: str, user_id: str, watchlist_id: str | None = None):
    from app.research.router import trigger_research
    logger.info(f"Triggering scheduled run for schedule {schedule_id} (watchlist: {watchlist_id})")
    await trigger_research(watchlist_id=watchlist_id, user_id=user_id, async_execution=True)

def register_schedule_job(schedule_id: str, cron_expression: str, user_id: str, watchlist_id: str | None = None):
    """Dynamically register or update a cron job in APScheduler."""
    try:
        scheduler.add_job(
            trigger_scheduled_run,
            CronTrigger.from_crontab(cron_expression),
            id=schedule_id,
            kwargs={"schedule_id": schedule_id, "user_id": user_id, "watchlist_id": watchlist_id},
            replace_existing=True
        )
        logger.info(f"Dynamically registered job {schedule_id} with cron '{cron_expression}'")
    except Exception as e:
        logger.error(f"Failed to register job {schedule_id}: {e}")

def unregister_schedule_job(schedule_id: str):
    """Remove a job from APScheduler."""
    try:
        if scheduler.get_job(schedule_id):
            scheduler.remove_job(schedule_id)
            logger.info(f"Unregistered job {schedule_id} from APScheduler")
    except Exception as e:
        logger.error(f"Failed to unregister job {schedule_id}: {e}")

async def start_scheduler():
    """Initializes APScheduler with active schedules from the database."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(ResearchScheduleModel).where(ResearchScheduleModel.is_active == True)
            res = await session.execute(stmt)
            schedules = res.scalars().all()
            
            for s in schedules:
                register_schedule_job(s.id, s.cron_expression, s.user_id, s.watchlist_id)
                    
        if not scheduler.running:
            scheduler.start()
            logger.info("APScheduler started successfully.")
    except Exception as e:
        logger.error(f"Failed to start APScheduler: {e}")

def stop_scheduler():
    """Stops APScheduler."""
    if scheduler.running:
        scheduler.shutdown()
