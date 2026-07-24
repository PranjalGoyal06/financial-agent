from __future__ import annotations

import logging
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Artifact

logger = logging.getLogger(__name__)


async def get_ticker_recommendation(
    session: AsyncSession,
    ticker: str,
) -> dict | None:
    """Retrieve the latest denormalized recommendation for a ticker.

    Reads from the ``artifacts`` Postgres table, filtering by tags,
    and parsing the metadata json.
    """
    ticker = ticker.upper()
    stmt = (
        select(Artifact)
        .where(
            Artifact.tags.like('%"type:ticker"%'),
            Artifact.tags.like(f'%"target:{ticker}"%')
        )
        .order_by(Artifact.created_at.desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    artifact = res.scalar_one_or_none()

    if not artifact:
        logger.debug("No prior research recommendations found for %s", ticker)
        return None

    try:
        metadata = json.loads(artifact.metadata_json)
    except Exception:
        metadata = {}

    recommendation = metadata.get("recommendation")
    confidence_score = metadata.get("confidence_score")

    logger.debug(
        "Retrieved recommendation for %s | recommendation=%s confidence=%s",
        ticker,
        recommendation,
        confidence_score,
    )
    return {
        "ticker": ticker,
        "recommendation": recommendation,
        "confidence_score": confidence_score,
        "last_updated": artifact.created_at,
        "run_id": artifact.source_ref_id,
    }
