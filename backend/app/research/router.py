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
from app.models import ResearchArtifact
from app.portfolio.lib import get_ticker_recommendation
from app.research.graph import build_research_graph
from app.watchlist.service import get_watchlist

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/research", tags=["Research"])

# Global memory map to track background research task states
RUN_STATUS: dict[str, Literal["running", "completed", "failed"]] = {}

# Compiled graph singleton
_research_graph = build_research_graph().compile()


# ── Background Task Runner ────────────────────────────────────────────────────


async def _run_research_graph(run_id: str, user_id: str) -> None:
    """Execute the compiled LangGraph workflow in the background."""
    RUN_STATUS[run_id] = "running"
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
        logger.info("Background deep research completed successfully | run_id=%s", run_id)
    except Exception as exc:
        RUN_STATUS[run_id] = "failed"
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
        # Fall back: check if artifacts already exist in Postgres for this run_id
        # (This handles server restarts where in-memory RUN_STATUS is lost)
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(ResearchArtifact.id).where(ResearchArtifact.run_id == run_id).limit(1)
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
    stmt = select(ResearchArtifact).where(
        ResearchArtifact.run_id == run_id,
        ResearchArtifact.artifact_type == artifact_type,
    )
    if target:
        stmt = stmt.where(ResearchArtifact.target == target.upper())

    res = await session.execute(stmt)
    artifact = res.scalar_one_or_none()

    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No artifact found for run_id='{run_id}', "
                f"type='{artifact_type}' and target='{target}'."
            ),
        )

    return {
        "run_id": artifact.run_id,
        "artifact_type": artifact.artifact_type,
        "target": artifact.target,
        "content_markdown": artifact.content_markdown,
        "evidence_pack": json.loads(artifact.evidence_pack_json),
        "recommendation": artifact.recommendation,
        "confidence_score": artifact.confidence_score,
        "created_at": artifact.created_at,
    }


# Import AsyncSessionLocal for background tasks
from app.db import AsyncSessionLocal
