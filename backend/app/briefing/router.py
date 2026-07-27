from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.briefing.schemas import BriefingResponse
from app.briefing.service import get_briefing_data
from app.config import settings
from app.db import get_session

router = APIRouter(prefix="/briefing", tags=["Briefing"])

# Simple in-memory cache: {user_id: (timestamp, BriefingResponse)}
_BRIEFING_CACHE: Dict[str, Tuple[datetime, BriefingResponse]] = {}
CACHE_TTL = timedelta(minutes=10)


@router.get("/", response_model=BriefingResponse)
async def get_dashboard_briefing(
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session),
) -> BriefingResponse:
    """Retrieve the full briefing zone payload for the dashboard."""
    now = datetime.now(timezone.utc)
    
    if user_id in _BRIEFING_CACHE:
        cached_time, cached_data = _BRIEFING_CACHE[user_id]
        if now - cached_time < CACHE_TTL:
            return cached_data

    data = await get_briefing_data(session, user_id)
    _BRIEFING_CACHE[user_id] = (now, data)
    return data
