from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import AsyncSessionLocal
from app.market_data.provider import normalize_ticker_symbol
from app.models import InstrumentModel
from app.research.state import ResearchState
from app.watchlist.service import get_watchlist

logger = logging.getLogger(__name__)


def _fetch_yf_metadata(ticker: str) -> dict:
    """Synchronous yfinance call to retrieve instrument metadata."""
    try:
        t = yf.Ticker(normalize_ticker_symbol(ticker))
        info = t.info
        
        market_cap = info.get("marketCap")
        market_cap_bucket = None
        if market_cap:
            if market_cap > 200_000_000_000:
                market_cap_bucket = "Large Cap"
            elif market_cap >= 50_000_000_000:
                market_cap_bucket = "Mid Cap"
            else:
                market_cap_bucket = "Small Cap"

        return {
            "canonical_ticker": ticker.split(".")[0],
            "display_name": info.get("shortName"),
            "company_name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": market_cap,
            "market_cap_bucket": market_cap_bucket,
            "country": info.get("country"),
            "currency": info.get("currency"),
            "exchange": info.get("exchange") or ("NSE" if ticker.upper().endswith(".NS") else "BSE"),
            "quote_type": info.get("quoteType"),
            "website": info.get("website"),
            "summary": info.get("longBusinessSummary"),
            "full_time_employees": info.get("fullTimeEmployees"),
            "raw_yfinance_info": info,
        }
    except Exception as exc:
        logger.warning("yfinance metadata fetch failed for %r: %s", ticker, exc)
        return {
            "canonical_ticker": ticker.split(".")[0],
            "display_name": ticker,
            "company_name": ticker,
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
        return inst.display_name or inst.company_name or inst.ticker, inst.sector

    # 2. Fall back to yfinance
    metadata = await asyncio.to_thread(_fetch_yf_metadata, ticker)
    display_name = metadata.get("display_name") or metadata.get("company_name") or ticker
    sector = metadata.get("sector") or "Diversified"

    # 3. Upsert into instruments table
    async with AsyncSessionLocal() as session:
        async with session.begin():
            insert_stmt = (
                pg_insert(InstrumentModel)
                .values(
                    ticker=ticker,
                    canonical_ticker=metadata.get("canonical_ticker"),
                    display_name=metadata.get("display_name"),
                    company_name=metadata.get("company_name"),
                    sector=metadata.get("sector"),
                    industry=metadata.get("industry"),
                    market_cap=metadata.get("market_cap"),
                    market_cap_bucket=metadata.get("market_cap_bucket"),
                    country=metadata.get("country"),
                    currency=metadata.get("currency"),
                    exchange=metadata.get("exchange"),
                    quote_type=metadata.get("quote_type"),
                    website=metadata.get("website"),
                    summary=metadata.get("summary"),
                    full_time_employees=metadata.get("full_time_employees"),
                    raw_yfinance_info=metadata.get("raw_yfinance_info", {}),
                    last_synced_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_update(
                    index_elements=["ticker"],
                    set_={
                        "canonical_ticker": metadata.get("canonical_ticker"),
                        "display_name": metadata.get("display_name"),
                        "company_name": metadata.get("company_name"),
                        "sector": metadata.get("sector"),
                        "industry": metadata.get("industry"),
                        "market_cap": metadata.get("market_cap"),
                        "market_cap_bucket": metadata.get("market_cap_bucket"),
                        "country": metadata.get("country"),
                        "currency": metadata.get("currency"),
                        "exchange": metadata.get("exchange"),
                        "quote_type": metadata.get("quote_type"),
                        "website": metadata.get("website"),
                        "summary": metadata.get("summary"),
                        "full_time_employees": metadata.get("full_time_employees"),
                        "raw_yfinance_info": metadata.get("raw_yfinance_info", {}),
                        "last_synced_at": datetime.now(timezone.utc),
                    },
                )
            )
            await session.execute(insert_stmt)

    logger.info("Resolved metadata for %s | sector=%s (saved to cache)", ticker, sector)
    return display_name, sector


async def plan_macro_sector(state: ResearchState) -> dict:
    """Planner Node 1: Resolves watchlist tickers and maps them to sectors.

    Retrieves the user's watchlist (holdings + watchlists), resolves the sector
    and metadata for each target ticker, and populates the sectors structure
    so that macro/sector collection can begin.
    """
    user_id = state.get("user_id") or "local-user"
    watchlist_id = state.get("watchlist_id")
    logger.info("Plan Macro/Sector Node starting | user_id=%s watchlist_id=%s run_id=%s", user_id, watchlist_id, state.get("run_id"))

    # 1. Fetch watchlist
    async with AsyncSessionLocal() as session:
        watchlist = await get_watchlist(session, user_id, watchlist_id)

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
        if sector == "Unknown":
            sector = "Diversified"
        ticker_to_sector[ticker] = sector
        sectors_set.add(sector)

    sectors = sorted(list(sectors_set))
    logger.info(
        "Plan Macro/Sector complete | watchlist=%s sectors=%s mappings=%s",
        watchlist,
        sectors,
        ticker_to_sector,
    )

    return {
        "tickers": watchlist,
        "sectors": sectors,
        "ticker_to_sector": ticker_to_sector,
    }


async def plan_tickers(state: ResearchState) -> dict:
    """Planner Node 2: Merges discovered tickers into the final target list.

    Runs after `discover_screen`. Resolves metadata for any newly discovered
    tickers. If a discovered ticker belongs to a sector that wasn't in the
    original watchlist, it will intentionally NOT be added to `sectors`, so
    it receives a degraded macro-only context during synthesis.
    """
    watchlist_tickers = state.get("tickers", [])
    discovered_tickers = state.get("discovered_tickers", [])
    
    if not discovered_tickers:
        logger.info("Plan Tickers Node: No discovered tickers to merge.")
        return {}

    logger.info("Plan Tickers Node: Resolving metadata for %d discovered tickers", len(discovered_tickers))
    
    # 1. Resolve sectors for discovered tickers
    tasks = [_resolve_ticker_sector(t) for t in discovered_tickers]
    results = await asyncio.gather(*tasks)

    # 2. Update structures
    # We must merge with the existing ticker_to_sector map
    existing_map = state.get("ticker_to_sector", {})
    new_map = dict(existing_map)
    
    for idx, ticker in enumerate(discovered_tickers):
        name, sector = results[idx]
        if sector == "Unknown":
            sector = "Diversified"
        new_map[ticker] = sector
        # Intentionally NOT adding to state["sectors"] to avoid out-of-band sector collection.
        # Ticker synthesis will gracefully handle missing sector synthesis.

    final_tickers = watchlist_tickers + discovered_tickers
    
    logger.info("Plan Tickers complete | final_tickers=%s", final_tickers)

    return {
        "tickers": final_tickers,
        "ticker_to_sector": new_map,
    }

