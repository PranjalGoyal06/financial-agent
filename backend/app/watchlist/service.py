from __future__ import annotations

import logging
import re

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HoldingModel, PortfolioModel, WatchlistItem, WatchlistModel

logger = logging.getLogger(__name__)


def create_slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


async def get_or_create_portfolio_watchlist(session: AsyncSession, user_id: str) -> WatchlistModel:
    stmt = select(WatchlistModel).where(
        WatchlistModel.user_id == user_id, 
        WatchlistModel.type == "portfolio"
    )
    res = await session.execute(stmt)
    wl = res.scalar_one_or_none()
    if not wl:
        wl = WatchlistModel(
            user_id=user_id,
            name="My Portfolio",
            slug="my-portfolio",
            type="portfolio"
        )
        session.add(wl)
        await session.commit()
    return wl


async def create_watchlist(session: AsyncSession, user_id: str, name: str) -> WatchlistModel:
    slug = create_slug(name)
    wl = WatchlistModel(
        user_id=user_id,
        name=name,
        slug=slug,
        type="custom"
    )
    session.add(wl)
    await session.flush()
    return wl


async def list_watchlists(session: AsyncSession, user_id: str) -> list[WatchlistModel]:
    stmt = select(WatchlistModel).where(WatchlistModel.user_id == user_id)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_watchlist(session: AsyncSession, user_id: str, watchlist_id: str | None = None) -> list[str]:
    """Retrieve all watchlisted tickers for a specific watchlist.
    
    If watchlist_id is None, defaults to the user's dynamic portfolio watchlist.
    """
    if not watchlist_id:
        wl = await get_or_create_portfolio_watchlist(session, user_id)
        watchlist_id = wl.id
        wl_type = "portfolio"
    else:
        stmt = select(WatchlistModel.type).where(WatchlistModel.id == watchlist_id)
        res = await session.execute(stmt)
        wl_type = res.scalar_one_or_none()
        if not wl_type:
            logger.warning("Watchlist not found | id=%s", watchlist_id)
            return []

    if wl_type == "portfolio":
        # Dynamic from holdings
        holdings_stmt = (
            select(HoldingModel.canonical_ticker)
            .join(PortfolioModel, HoldingModel.portfolio_id == PortfolioModel.id)
            .where(PortfolioModel.user_id == user_id)
        )
        holdings_res = await session.execute(holdings_stmt)
        tickers = {row[0] for row in holdings_res.all() if row[0]}
    else:
        # Custom from items
        watchlist_stmt = select(WatchlistItem.canonical_ticker).where(
            WatchlistItem.watchlist_id == watchlist_id
        )
        watchlist_res = await session.execute(watchlist_stmt)
        tickers = {row[0] for row in watchlist_res.all() if row[0]}

    all_tickers = sorted(list(tickers))
    logger.debug(
        "Retrieved watchlist | watchlist_id=%s count=%d",
        watchlist_id,
        len(all_tickers),
    )
    return all_tickers


async def add_to_watchlist(
    session: AsyncSession,
    watchlist_id: str,
    canonical_ticker: str,
    exchange: str = "NSE",
) -> WatchlistItem:
    """Add a ticker to a custom watchlist."""
    canonical_ticker = canonical_ticker.upper()
    exchange = exchange.upper()

    stmt = select(WatchlistItem).where(
        WatchlistItem.watchlist_id == watchlist_id,
        WatchlistItem.canonical_ticker == canonical_ticker,
    )
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return existing

    item = WatchlistItem(
        watchlist_id=watchlist_id,
        canonical_ticker=canonical_ticker,
        exchange=exchange,
    )
    session.add(item)
    await session.flush()
    return item


async def remove_from_watchlist(
    session: AsyncSession,
    watchlist_id: str,
    canonical_ticker: str,
) -> bool:
    """Remove a ticker from a custom watchlist."""
    canonical_ticker = canonical_ticker.upper()
    stmt = (
        delete(WatchlistItem)
        .where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.canonical_ticker == canonical_ticker,
        )
        .returning(WatchlistItem.id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none() is not None


async def rename_watchlist(session: AsyncSession, watchlist_id: str, new_name: str) -> bool:
    """Rename a custom watchlist."""
    stmt = (
        update(WatchlistModel)
        .where(
            WatchlistModel.id == watchlist_id, 
            WatchlistModel.type == "custom"
        )
        .values(name=new_name, slug=create_slug(new_name))
        .returning(WatchlistModel.id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none() is not None


async def delete_watchlist(session: AsyncSession, watchlist_id: str) -> bool:
    """Delete a custom watchlist and its items cascade automatically."""
    stmt = (
        delete(WatchlistModel)
        .where(
            WatchlistModel.id == watchlist_id, 
            WatchlistModel.type == "custom"
        )
        .returning(WatchlistModel.id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none() is not None
