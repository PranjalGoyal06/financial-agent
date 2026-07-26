import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import ResearchScheduleModel

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def trigger_scheduled_run(schedule_id: str, user_id: str):
    from app.research.router import trigger_research
    from app.config import settings
    logger.info(f"Triggering scheduled run for schedule {schedule_id}")
    # Run the background task by simulating the trigger
    await trigger_research(user_id=user_id)

async def start_scheduler():
    """Initializes APScheduler with active schedules from the database."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(ResearchScheduleModel).where(ResearchScheduleModel.is_active == True)
            res = await session.execute(stmt)
            schedules = res.scalars().all()
            
            for s in schedules:
                try:
                    scheduler.add_job(
                        trigger_scheduled_run,
                        CronTrigger.from_crontab(s.cron_expression),
                        id=s.id,
                        kwargs={"schedule_id": s.id, "user_id": s.user_id},
                        replace_existing=True
                    )
                except Exception as e:
                    logger.error(f"Failed to add schedule {s.id} to apscheduler: {e}")
                    
        scheduler.start()
        logger.info("APScheduler started successfully.")
    except Exception as e:
        logger.error(f"Failed to start APScheduler: {e}")

def stop_scheduler():
    """Stops APScheduler."""
    if scheduler.running:
        scheduler.shutdown()
