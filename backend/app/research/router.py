from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session, AsyncSessionLocal
from app.models import Artifact, ResearchRunModel, ResearchRunEventModel, ResearchScheduleModel, utc_now
from app.portfolio.lib import get_ticker_recommendation
from app.research.graph import build_research_graph
from app.watchlist.service import get_watchlist
from app.research.logger import get_run_logger, get_sse_queue, cleanup_sse_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/research", tags=["Research"])

# Compiled graph singleton
_research_graph = build_research_graph().compile()

# ── Background Task Runner ────────────────────────────────────────────────────

async def _run_research_graph(run_id: str, user_id: str, watchlist_id: str | None = None) -> None:
    """Execute the compiled LangGraph workflow in the background."""
    run_logger = get_run_logger(run_id)
    run_logger.log_event("workflow", "node_start", f"Starting background deep research run {run_id}")
    logger.info("Starting background deep research | run_id=%s user_id=%s watchlist_id=%s", run_id, user_id, watchlist_id)
    
    # Register run in DB
    try:
        async with AsyncSessionLocal() as session:
            db_run = ResearchRunModel(id=run_id, user_id=user_id, watchlist_id=watchlist_id, status="running")
            session.add(db_run)
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to create ResearchRunModel for {run_id}: {e}")
        return

    final_status = "failed"
    try:
        initial_state: dict[str, Any] = {
            "run_id": run_id,
            "user_id": user_id,
            "watchlist_id": watchlist_id,
            "tickers": [],
            "sectors": [],
            "ticker_to_sector": {},
            "macro_evidence": None,
            "sector_evidence": {},
            "ticker_evidence": {},
            "portfolio_evidence": None,
            "macro_synthesis": None,
            "sector_synthesis": {},
            "ticker_synthesis": {},
            "portfolio_synthesis": None,
            "errors": [],
        }
        await _research_graph.ainvoke(initial_state)
        final_status = "completed"
        run_logger.log_event("workflow", "node_complete", f"Background deep research run {run_id} completed successfully")
        logger.info("Background deep research completed successfully | run_id=%s", run_id)
    except Exception as exc:
        final_status = "failed"
        run_logger.log_exception("workflow", exc, f"Workflow execution failed for run_id={run_id}")
        logger.exception("Background deep research run failed | run_id=%s: %s", run_id, exc)
    finally:
        # 1. Update ResearchRunModel status
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(ResearchRunModel).where(ResearchRunModel.id == run_id)
                res = await session.execute(stmt)
                db_run = res.scalar_one_or_none()
                if db_run:
                    db_run.status = final_status
                    db_run.completed_at = utc_now()
                    await session.commit()
        except Exception as e:
            logger.error(f"Failed to update ResearchRunModel status for {run_id}: {e}")

        # 2. Emit terminal event to queue to unblock SSE subscribers
        run_logger.log_event("workflow", "run_completed" if final_status == "completed" else "run_failed", f"Run {final_status}")
        
        # 3. Clean up memory queue after a short delay so subscribers can drain terminal event
        await asyncio.sleep(5)
        cleanup_sse_queue(run_id)

# ── REST Endpoints ────────────────────────────────────────────────────────────

@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_research(
    watchlist_id: str | None = Query(default=None, description="Optional ID of a specific watchlist to run against"),
    user_id: str = settings.default_user_id,
) -> dict[str, str]:
    """Trigger a deep research analysis workflow run in the background."""
    run_id = f"run_{uuid4().hex[:12]}"
    
    # Spawn background task
    asyncio.create_task(_run_research_graph(run_id, user_id, watchlist_id))
    
    return {
        "run_id": run_id,
        "status": "running",
    }

@router.get("/status/{run_id}")
async def get_run_status(run_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """Retrieve the status of a triggered deep research run."""
    stmt = select(ResearchRunModel.status).where(ResearchRunModel.id == run_id)
    res = await session.execute(stmt)
    status_val = res.scalar_one_or_none()
    
    if status_val is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run ID '{run_id}' not found.",
        )
        
    return {
        "run_id": run_id,
        "status": status_val,
    }

@router.get("/stream/{run_id}")
async def stream_run_events(run_id: str, session: AsyncSession = Depends(get_session)):
    """SSE endpoint for live-streaming run events, replays backlog first."""
    
    # Check if run exists
    stmt = select(ResearchRunModel).where(ResearchRunModel.id == run_id)
    res = await session.execute(stmt)
    db_run = res.scalar_one_or_none()
    
    if not db_run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    async def event_generator():
        # 1. Backlog Replay
        async with AsyncSessionLocal() as replay_session:
            backlog_stmt = select(ResearchRunEventModel).where(ResearchRunEventModel.run_id == run_id).order_by(ResearchRunEventModel.created_at.asc())
            backlog_res = await replay_session.execute(backlog_stmt)
            for ev in backlog_res.scalars():
                data = {
                    "timestamp": ev.created_at.isoformat(),
                    "run_id": ev.run_id,
                    "node": ev.node,
                    "target": ev.target,
                    "level": ev.level,
                    "event_type": ev.event_type,
                    "summary": ev.summary,
                    "payload": ev.payload_json,
                }
                yield f"event: node_event\ndata: {json.dumps(data)}\n\n"
        
        # Check if run is already completed before entering live subscription
        async with AsyncSessionLocal() as check_session:
            check_res = await check_session.execute(select(ResearchRunModel.status).where(ResearchRunModel.id == run_id))
            status_val = check_res.scalar_one_or_none()
            if status_val in ("completed", "failed"):
                return
                
        # 2. Live Subscription
        queue = get_sse_queue(run_id)
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=2.0)
                yield f"event: node_event\ndata: {json.dumps(event)}\n\n"
                queue.task_done()
                if event.get("event_type") in ("run_completed", "run_failed"):
                    break
            except asyncio.TimeoutError:
                # Keep-alive or check run status
                async with AsyncSessionLocal() as check_session:
                    check_res = await check_session.execute(select(ResearchRunModel.status).where(ResearchRunModel.id == run_id))
                    if check_res.scalar_one_or_none() in ("completed", "failed"):
                        break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/events/{run_id}")
async def get_run_events(
    run_id: str,
    after: str | None = Query(default=None, description="ISO timestamp cursor"),
    session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """Polling fallback for clients dropping SSE."""
    stmt = select(ResearchRunEventModel).where(ResearchRunEventModel.run_id == run_id)
    if after:
        try:
            after_dt = datetime.fromisoformat(after.replace("Z", "+00:00"))
            stmt = stmt.where(ResearchRunEventModel.created_at > after_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid ISO timestamp format for 'after' parameter")
            
    stmt = stmt.order_by(ResearchRunEventModel.created_at.asc())
    res = await session.execute(stmt)
    events = res.scalars().all()
    
    return {
        "run_id": run_id,
        "events": [
            {
                "timestamp": ev.created_at.isoformat(),
                "node": ev.node,
                "target": ev.target,
                "event_type": ev.event_type,
                "level": ev.level,
                "summary": ev.summary,
                "payload": ev.payload_json,
            }
            for ev in events
        ]
    }

@router.get("/runs")
async def list_runs(
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session)
) -> dict[str, list[dict]]:
    """List historical research runs."""
    stmt = select(ResearchRunModel).where(ResearchRunModel.user_id == user_id).order_by(desc(ResearchRunModel.started_at)).limit(50)
    res = await session.execute(stmt)
    runs = res.scalars().all()
    
    return {
        "runs": [
            {
                "id": r.id,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in runs
        ]
    }

@router.post("/schedule")
async def create_schedule(
    cron_expression: str,
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """Create a scheduled run."""
    db_sched = ResearchScheduleModel(user_id=user_id, cron_expression=cron_expression)
    session.add(db_sched)
    await session.commit()
    
    return {
        "id": db_sched.id,
        "cron_expression": db_sched.cron_expression,
        "is_active": db_sched.is_active,
    }

@router.get("/schedules")
async def list_schedules(
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session)
) -> dict[str, list[dict]]:
    """List active scheduled runs."""
    stmt = select(ResearchScheduleModel).where(ResearchScheduleModel.user_id == user_id)
    res = await session.execute(stmt)
    schedules = res.scalars().all()
    
    return {
        "schedules": [
            {
                "id": s.id,
                "cron_expression": s.cron_expression,
                "is_active": s.is_active,
            }
            for s in schedules
        ]
    }

@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    """Delete a scheduled run."""
    stmt = delete(ResearchScheduleModel).where(ResearchScheduleModel.id == schedule_id)
    await session.execute(stmt)
    await session.commit()
    return {"status": "deleted"}


@router.get("/recommendations")
async def get_all_recommendations(
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session),
) -> dict[str, list[dict]]:
    """Retrieve the latest recommendations for all tickers in the user watchlist."""
    watchlist = await get_watchlist(session, user_id)
    
    if not watchlist:
        return {"recommendations": []}

    recs = []
    for ticker in watchlist:
        rec_data = await get_ticker_recommendation(session, ticker)
        if rec_data:
            recs.append(rec_data)
            
    return {"recommendations": recs}


@router.get("/artifact/{run_id}/{artifact_type}")
async def get_research_artifact(
    run_id: str,
    artifact_type: Literal["macro", "sector", "ticker", "portfolio"],
    target: str | None = Query(default=None, description="Ticker or sector name (optional)"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve the markdown report and evidence pack for a specific research product."""
    stmt = select(Artifact).where(Artifact.source_ref_id == run_id)
    res = await session.execute(stmt)
    artifacts = res.scalars().all()
    
    target_upper = target.upper() if target else None
    
    found_artifact = None
    metadata = {}
    for a in artifacts:
        meta = a.metadata_json if isinstance(a.metadata_json, dict) else json.loads(a.metadata_json)
        if meta.get("artifact_type") == artifact_type and meta.get("target") == target_upper:
            found_artifact = a
            metadata = meta
            break

    if not found_artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No artifact found for run_id='{run_id}', "
                f"type='{artifact_type}' and target='{target}'."
            ),
        )

    evidence_pack = []
    try:
        ep_json = metadata.get("evidence_pack_json")
        if ep_json:
            evidence_pack = ep_json if isinstance(ep_json, list) else json.loads(ep_json)
    except Exception:
        pass

    return {
        "run_id": found_artifact.source_ref_id,
        "artifact_type": metadata.get("artifact_type"),
        "target": metadata.get("target"),
        "content_markdown": found_artifact.content_markdown,
        "evidence_pack": evidence_pack,
        "recommendation": metadata.get("recommendation"),
        "confidence_score": metadata.get("confidence_score"),
        "created_at": found_artifact.created_at.isoformat(),
    }
