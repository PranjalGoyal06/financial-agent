from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HoldingModel, PortfolioModel, WatchlistItem

logger = logging.getLogger(__name__)


async def get_watchlist(session: AsyncSession, user_id: str) -> list[str]:
    """Retrieve all watchlisted tickers for a user.

    By default, this returns a union of:
      1. Canonical tickers from the user's holdings (current portfolio)
      2. Tickers explicitly added to the user's watchlist_items table

    This ensures that the overnight analysis automatically includes all
    currently held assets as well as custom watched tickers, without
    requiring duplicate data entry.
    """
    # ── 1. Get tickers from holdings ──────────────────────────────────────────
    holdings_stmt = (
        select(HoldingModel.canonical_ticker)
        .join(PortfolioModel, HoldingModel.portfolio_id == PortfolioModel.id)
        .where(PortfolioModel.user_id == user_id)
    )
    holdings_res = await session.execute(holdings_stmt)
    holdings_tickers = {row[0] for row in holdings_res.all() if row[0]}

    # ── 2. Get tickers from watchlist_items ───────────────────────────────────
    watchlist_stmt = select(WatchlistItem.canonical_ticker).where(
        WatchlistItem.user_id == user_id
    )
    watchlist_res = await session.execute(watchlist_stmt)
    watchlist_tickers = {row[0] for row in watchlist_res.all() if row[0]}

    # Return union as sorted list
    all_tickers = sorted(list(holdings_tickers | watchlist_tickers))
    logger.debug(
        "Retrieved watchlist for user=%s | count=%d tickers=%s",
        user_id,
        len(all_tickers),
        all_tickers,
    )
    return all_tickers


async def add_to_watchlist(
    session: AsyncSession,
    user_id: str,
    canonical_ticker: str,
    exchange: str = "NSE",
) -> WatchlistItem:
    """Add a ticker to the user's watchlist.

    No-op if the ticker is already in the watchlist_items table.
    """
    canonical_ticker = canonical_ticker.upper()
    exchange = exchange.upper()

    # Check if already exists
    stmt = select(WatchlistItem).where(
        WatchlistItem.user_id == user_id,
        WatchlistItem.canonical_ticker == canonical_ticker,
    )
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        logger.debug(
            "Ticker already in watchlist_items | user=%s ticker=%s",
            user_id,
            canonical_ticker,
        )
        return existing

    # Create new entry
    item = WatchlistItem(
        user_id=user_id,
        canonical_ticker=canonical_ticker,
        exchange=exchange,
    )
    session.add(item)
    await session.flush()  # populate ID/added_at
    logger.info(
        "Added ticker to watchlist_items | user=%s ticker=%s exchange=%s",
        user_id,
        canonical_ticker,
        exchange,
    )
    return item


async def remove_from_watchlist(
    session: AsyncSession,
    user_id: str,
    canonical_ticker: str,
) -> bool:
    """Remove a ticker from the user's watchlist.

    Returns True if an entry was deleted, False if not found.
    """
    canonical_ticker = canonical_ticker.upper()
    stmt = (
        delete(WatchlistItem)
        .where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.canonical_ticker == canonical_ticker,
        )
        .returning(WatchlistItem.id)
    )
    res = await session.execute(stmt)
    deleted_id = res.scalar_one_or_none()
    
    if deleted_id:
        logger.info(
            "Removed ticker from watchlist_items | user=%s ticker=%s id=%s",
            user_id,
            canonical_ticker,
            deleted_id,
        )
        return True
    
    logger.debug(
        "Ticker not found in watchlist_items | user=%s ticker=%s",
        user_id,
        canonical_ticker,
    )
    return False
