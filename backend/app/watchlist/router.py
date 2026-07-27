from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.config import settings
from app.watchlist.service import (
    list_watchlists,
    get_or_create_portfolio_watchlist,
    create_watchlist,
    get_watchlist,
    add_to_watchlist,
    remove_from_watchlist,
    rename_watchlist,
    delete_watchlist,
)

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])

class WatchlistCreateRequest(BaseModel):
    name: str

class WatchlistItemRequest(BaseModel):
    ticker: str
    exchange: str = "NSE"


@router.get("")
async def get_watchlists_endpoint(
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session)
):
    """Retrieve all watchlists for the user."""
    # Ensure portfolio watchlist exists
    await get_or_create_portfolio_watchlist(session, user_id)
    
    watchlists = await list_watchlists(session, user_id)
    return {
        "watchlists": [
            {
                "id": wl.id,
                "name": wl.name,
                "slug": wl.slug,
                "type": wl.type
            } for wl in watchlists
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_watchlist_endpoint(
    req: WatchlistCreateRequest,
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session)
):
    wl = await create_watchlist(session, user_id, req.name)
    await session.commit()
    return {"id": wl.id, "name": wl.name, "slug": wl.slug, "type": wl.type}


@router.patch("/{watchlist_id}")
async def rename_watchlist_endpoint(
    watchlist_id: str,
    req: WatchlistCreateRequest,
    session: AsyncSession = Depends(get_session)
):
    success = await rename_watchlist(session, watchlist_id, req.name)
    if not success:
        raise HTTPException(status_code=404, detail="Custom watchlist not found or cannot be modified")
    await session.commit()
    return {"message": "Watchlist renamed"}


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_endpoint(
    watchlist_id: str,
    session: AsyncSession = Depends(get_session)
):
    success = await delete_watchlist(session, watchlist_id)
    if not success:
        raise HTTPException(status_code=404, detail="Custom watchlist not found or cannot be deleted")
    await session.commit()


@router.get("/{watchlist_id}/items")
async def get_watchlist_items_endpoint(
    watchlist_id: str,
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session)
):
    tickers = await get_watchlist(session, user_id, watchlist_id)
    return {"tickers": tickers}


@router.post("/{watchlist_id}/items", status_code=status.HTTP_201_CREATED)
async def add_watchlist_item_endpoint(
    watchlist_id: str,
    req: WatchlistItemRequest,
    session: AsyncSession = Depends(get_session)
):
    item = await add_to_watchlist(session, watchlist_id, req.ticker, req.exchange)
    await session.commit()
    return {"id": item.id, "ticker": item.canonical_ticker, "exchange": item.exchange}


@router.delete("/{watchlist_id}/items/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_watchlist_item_endpoint(
    watchlist_id: str,
    ticker: str,
    session: AsyncSession = Depends(get_session)
):
    success = await remove_from_watchlist(session, watchlist_id, ticker)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found in watchlist")
    await session.commit()

