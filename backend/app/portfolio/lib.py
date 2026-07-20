from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ResearchArtifact

logger = logging.getLogger(__name__)


async def get_ticker_recommendation(
    session: AsyncSession,
    ticker: str,
) -> dict | None:
    """Retrieve the latest denormalized recommendation for a ticker.

    Reads from the ``research_artifacts`` Postgres table directly (single
    source of truth), sorting by created_at descending.
    """
    ticker = ticker.upper()
    stmt = (
        select(ResearchArtifact)
        .where(
            ResearchArtifact.artifact_type == "ticker",
            ResearchArtifact.target == ticker,
        )
        .order_by(ResearchArtifact.created_at.desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    artifact = res.scalar_one_or_none()

    if not artifact:
        logger.debug("No prior research recommendations found for %s", ticker)
        return None

    logger.debug(
        "Retrieved recommendation for %s | recommendation=%s confidence=%s",
        ticker,
        artifact.recommendation,
        artifact.confidence_score,
    )
    return {
        "ticker": ticker,
        "recommendation": artifact.recommendation,
        "confidence_score": artifact.confidence_score,
        "last_updated": artifact.created_at,
    }
