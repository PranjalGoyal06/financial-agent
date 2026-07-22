from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.briefing.schemas import BriefingResponse
from app.briefing.service import get_briefing_data
from app.config import settings
from app.db import get_session

router = APIRouter(prefix="/briefing", tags=["Briefing"])


@router.get("/", response_model=BriefingResponse)
async def get_dashboard_briefing(
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session),
) -> BriefingResponse:
    """Retrieve the full briefing zone payload for the dashboard."""
    return await get_briefing_data(session, user_id)
