from __future__ import annotations

import asyncio
import json

from langchain_core.tools import tool

from app.config import settings
from app.db import AsyncSessionLocal
from app.watchlist.service import list_watchlists, get_watchlist


_LIST_DESC = (
    "List all available watchlists for the user. Returns a JSON array of "
    "objects containing 'id', 'name', 'slug', and 'type' (e.g. 'portfolio' "
    "or 'custom'). Use this tool when you need to know what watchlists the "
    "user has configured, or when resolving a watchlist name."
)

@tool(description=_LIST_DESC)
async def list_watchlists_tool() -> str:
    """List all of the user's configured watchlists."""
    async with AsyncSessionLocal() as session:
        watchlists = await list_watchlists(session, settings.default_user_id)
        # Also ensure the default portfolio is included or retrieved
        # list_watchlists already lists all created watchlists for the user
        
    return json.dumps([
        {
            "id": wl.id,
            "name": wl.name,
            "slug": wl.slug,
            "type": wl.type
        } for wl in watchlists
    ])


_GET_ITEMS_DESC = (
    "Retrieve all the tickers within a specific watchlist. You must provide "
    "the exact watchlist_id. Returns a JSON array of ticker strings (e.g., "
    "['INFY.NS', 'TCS.NS']). Use this tool to inspect what is inside a watchlist."
)

@tool(description=_GET_ITEMS_DESC)
async def get_watchlist_items_tool(watchlist_id: str) -> str:
    """Retrieve the tickers inside a specific watchlist by its ID."""
    async with AsyncSessionLocal() as session:
        tickers = await get_watchlist(session, settings.default_user_id, watchlist_id=watchlist_id)
    return json.dumps(tickers)


list_watchlists_tool.handle_tool_error = True
get_watchlist_items_tool.handle_tool_error = True

WATCHLIST_TOOLS = [
    list_watchlists_tool,
    get_watchlist_items_tool,
]
