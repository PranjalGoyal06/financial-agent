import os
from typing import List, Dict, Optional

from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func

from app.db import get_session
from app.models import InstrumentModel

router = APIRouter()

class StockResponse(BaseModel):
    symbol: str
    name: str
    isin: Optional[str] = None
    series: Optional[str] = None
    exchange: Optional[str] = "NSE"


@router.get("/stocks", response_model=List[StockResponse])
async def search_stocks(q: str = Query(""), session: AsyncSession = Depends(get_session)):
    """Search stocks by symbol or name in the local database. Returns top 10 results."""
    query = q.strip()
    if not query:
        return []
        
    search_term = f"%{query}%"
    
    stmt = (
        select(InstrumentModel)
        .where(
            or_(
                InstrumentModel.ticker.ilike(search_term),
                InstrumentModel.display_name.ilike(search_term),
                InstrumentModel.company_name.ilike(search_term),
            )
        )
        .order_by(InstrumentModel.market_cap.desc().nulls_last())
        .limit(10)
    )
    
    res = await session.execute(stmt)
    instruments = res.scalars().all()
    
    results = []
    for inst in instruments:
        results.append({
            "symbol": inst.ticker,
            "name": inst.display_name or inst.company_name or inst.ticker,
            "isin": inst.isin,
            "series": inst.series,
            "exchange": inst.exchange or "NSE",
        })
        
    return results
