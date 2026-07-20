from __future__ import annotations

import json

from langchain_core.tools import ToolException, tool

from app.db import AsyncSessionLocal
from app.portfolio.lib import get_ticker_recommendation

_REC_DESC = (
    "Retrieve the latest deep research recommendation and analysis summary "
    "for an Indian equity ticker. Use this to review prior research conclusions, "
    "target prices, and confidence levels. Ticker must end with .NS or .BO."
)


@tool(description=_REC_DESC)
async def get_ticker_recommendation_tool(ticker: str) -> str:
    """Retrieve the latest deep research recommendation and confidence rating for a ticker."""
    ticker = ticker.upper()
    try:
        async with AsyncSessionLocal() as session:
            rec_data = await get_ticker_recommendation(session, ticker)
            
        if not rec_data:
            return json.dumps({
                "ticker": ticker,
                "recommendation": "insufficient_data",
                "confidence_score": 0,
                "message": f"No prior deep research artifact found for '{ticker}'.",
            })
            
        # Serialise date fields to ISO strings
        if "last_updated" in rec_data and rec_data["last_updated"]:
            rec_data["last_updated"] = rec_data["last_updated"].isoformat()
            
        return json.dumps(rec_data)
    except Exception as exc:
        raise ToolException(f"Failed to retrieve ticker recommendation: {exc}") from exc
