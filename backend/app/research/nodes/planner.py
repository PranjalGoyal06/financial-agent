from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import AsyncSessionLocal
from app.models import InstrumentModel
from app.research.state import ResearchState
from app.watchlist.service import get_watchlist

logger = logging.getLogger(__name__)


def _fetch_yf_metadata(ticker: str) -> dict:
    """Synchronous yfinance call to retrieve sector, industry, and name metadata."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector") or "Diversified",
            "industry": info.get("industry") or "Diversified",
            "exchange": "NSE" if ticker.upper().endswith(".NS") else "BSE",
        }
    except Exception as exc:
        logger.warning("yfinance metadata fetch failed for %r: %s", ticker, exc)
        return {
            "name": ticker,
            "sector": "Unknown",
            "industry": "Unknown",
            "exchange": "NSE" if ticker.upper().endswith(".NS") else "BSE",
        }


async def _resolve_ticker_sector(ticker: str) -> tuple[str, str]:
    """Retrieve name and sector for a ticker.

    Tries to read from the local ``instruments`` cache table first.
    If missing or sector is null, falls back to yfinance and updates the cache.
    """
    ticker = ticker.upper()
    
    # 1. Check local DB cache
    async with AsyncSessionLocal() as session:
        stmt = select(InstrumentModel).where(InstrumentModel.ticker == ticker)
        res = await session.execute(stmt)
        inst = res.scalar_one_or_none()

    if inst and inst.sector and inst.sector != "Unknown":
        return inst.name, inst.sector

    # 2. Fall back to yfinance
    metadata = await asyncio.to_thread(_fetch_yf_metadata, ticker)
    name = metadata["name"]
    sector = metadata["sector"]

    # 3. Upsert into instruments table
    async with AsyncSessionLocal() as session:
        async with session.begin():
            insert_stmt = (
                pg_insert(InstrumentModel)
                .values(
                    ticker=ticker,
                    name=name,
                    exchange=metadata["exchange"],
                    sector=sector,
                    industry=metadata["industry"],
                    asset_class="Equity",
                    last_synced_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_update(
                    index_elements=["ticker"],
                    set_={
                        "name": name,
                        "sector": sector,
                        "industry": metadata["industry"],
                        "last_synced_at": datetime.now(timezone.utc),
                    },
                )
            )
            await session.execute(insert_stmt)

    logger.info("Resolved metadata for %s | sector=%s (saved to cache)", ticker, sector)
    return name, sector


async def plan_node(state: ResearchState) -> dict:
    """Planner Node: Resolves watchlist tickers and maps them to sectors.

    Retrieves the user's watchlist (holdings + watchlists), resolves the sector
    and metadata for each target ticker, and populates the targets structure.
    """
    user_id = state.get("user_id") or "local-user"
    logger.info("Planner Node starting | user_id=%s run_id=%s", user_id, state.get("run_id"))

    # 1. Fetch watchlist
    async with AsyncSessionLocal() as session:
        watchlist = await get_watchlist(session, user_id)

    if not watchlist:
        msg = f"Watchlist is empty for user_id={user_id}. Nothing to analyze."
        logger.warning(msg)
        return {
            "tickers": [],
            "sectors": [],
            "ticker_to_sector": {},
            "errors": [msg],
        }

    # 2. Resolve sectors in parallel
    tasks = [_resolve_ticker_sector(t) for t in watchlist]
    results = await asyncio.gather(*tasks)

    # 3. Build structures
    ticker_to_sector = {}
    sectors_set = set()
    for idx, ticker in enumerate(watchlist):
        name, sector = results[idx]
        # Ignore tickers that we couldn't resolve sector for (marked as Unknown)
        # unless they are the only ones, in which case we default to "Diversified"
        if sector == "Unknown":
            sector = "Diversified"
        ticker_to_sector[ticker] = sector
        sectors_set.add(sector)

    sectors = sorted(list(sectors_set))
    logger.info(
        "Planner Node complete | tickers=%s sectors=%s mappings=%s",
        watchlist,
        sectors,
        ticker_to_sector,
    )

    return {
        "tickers": watchlist,
        "sectors": sectors,
        "ticker_to_sector": ticker_to_sector,
    }
