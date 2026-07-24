from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Artifact
from app.portfolio.lib import get_ticker_recommendation
from app.research.graph import build_research_graph
from app.watchlist.service import get_watchlist

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/research", tags=["Research"])

# Global memory map to track background research task states
RUN_STATUS: dict[str, Literal["running", "completed", "failed"]] = {}

# Compiled graph singleton
_research_graph = build_research_graph().compile()


from app.research.logger import get_run_logger, read_run_logs

# ── Background Task Runner ────────────────────────────────────────────────────


async def _run_research_graph(run_id: str, user_id: str) -> None:
    """Execute the compiled LangGraph workflow in the background."""
    RUN_STATUS[run_id] = "running"
    run_logger = get_run_logger(run_id)
    run_logger.log_event("workflow", "node_start", f"Starting background deep research run {run_id}")
    logger.info("Starting background deep research | run_id=%s user_id=%s", run_id, user_id)
    
    try:
        initial_state: dict[str, Any] = {
            "run_id": run_id,
            "user_id": user_id,
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
        RUN_STATUS[run_id] = "completed"
        run_logger.log_event("workflow", "node_complete", f"Background deep research run {run_id} completed successfully")
        logger.info("Background deep research completed successfully | run_id=%s", run_id)
    except Exception as exc:
        RUN_STATUS[run_id] = "failed"
        run_logger.log_exception("workflow", exc, f"Workflow execution failed for run_id={run_id}")
        logger.exception("Background deep research run failed | run_id=%s: %s", run_id, exc)


# ── REST Endpoints ────────────────────────────────────────────────────────────


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_research(
    user_id: str = settings.default_user_id,
) -> dict[str, str]:
    """Trigger a deep research analysis workflow run in the background.

    Returns the generated run ID immediately.
    """
    run_id = f"run_{uuid4().hex[:12]}"
    
    # Spawn background task
    asyncio.create_task(_run_research_graph(run_id, user_id))
    
    return {
        "run_id": run_id,
        "status": "running",
    }


@router.get("/status/{run_id}")
async def get_run_status(run_id: str) -> dict[str, str]:
    """Retrieve the status of a triggered deep research run."""
    current_status = RUN_STATUS.get(run_id)
    
    if current_status is None:
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Artifact.id).where(Artifact.source_ref_id == run_id).limit(1)
                res = await session.execute(stmt)
                if res.scalar_one_or_none():
                    return {"run_id": run_id, "status": "completed"}
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run ID '{run_id}' not found.",
        )
        
    return {
        "run_id": run_id,
        "status": current_status,
    }


@router.get("/logs/{run_id}")
async def get_run_logs(
    run_id: str,
    node: str | None = Query(default=None, description="Filter logs by node name"),
    event_type: str | None = Query(default=None, description="Filter logs by event type"),
) -> dict[str, Any]:
    """Retrieve Tier-1 system-level debug logs for a research run."""
    logs = read_run_logs(run_id)
    
    if node:
        logs = [l for l in logs if l.get("node") == node]
    if event_type:
        logs = [l for l in logs if l.get("event_type") == event_type]

    return {
        "run_id": run_id,
        "total_events": len(logs),
        "logs": logs,
    }


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
        meta = json.loads(a.metadata_json)
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
        if metadata.get("evidence_pack_json"):
            evidence_pack = json.loads(metadata["evidence_pack_json"])
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
        "created_at": found_artifact.created_at,
    }


# Import AsyncSessionLocal for background tasks
from app.db import AsyncSessionLocal
