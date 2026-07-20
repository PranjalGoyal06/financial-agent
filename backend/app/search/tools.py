from __future__ import annotations

import json

from langchain_core.tools import ToolException, tool

from app.search.client import search

_SEARCH_DESC = (
    "Search the web for stock news, financial events, macro updates, "
    "and company disclosures. Input should be a specific search query "
    "string. Results are cached and returned in a prompt-ready list format "
    "with citations."
)


@tool(description=_SEARCH_DESC)
async def web_search_tool(query: str) -> str:
    """Search the web for stock news and financial events."""
    try:
        items = await search(query, max_results=5)
        # Normalise list into a serialised JSON array for the LLM
        return json.dumps([item.model_dump(mode="json") for item in items])
    except Exception as exc:
        raise ToolException(f"Search tool failed: {exc}") from exc
