from __future__ import annotations

import asyncio
import json

from langchain_core.tools import tool, ToolException

from app.market_data.provider import (
    ProviderError,
    TickerNotFoundError,
    YFinanceProvider,
)
from app.market_data.resolver import resolve_asset
from app.market_data.schemas import HistoricalDataResponse, MarketQuote

# Singleton provider — same as the one used by the router.
_provider = YFinanceProvider()

# ── Tool descriptions ─────────────────────────────────────────────────────────
#
# These strings are the primary tool-selection signal for the LLM. Keep them
# precise: wrong descriptions cause the agent to pick the wrong tool or skip
# one it should call. Each description names the exchange suffix convention
# so the agent knows to pass INFY.NS, not just INFY.

_RESOLVE_DESC = (
    "Resolve a free-text company name or alias to one or more NSE/BSE ticker "
    "candidates. Use this FIRST when you have a company name but not a ticker. "
    "Ambiguous names (e.g. 'tata motors') always return both NSE (.NS) and BSE "
    "(.BO) candidates — pick the NSE one unless the user specifies BSE. "
    "Returns JSON with a 'candidates' list each having 'canonical_ticker', "
    "'exchange', 'name', and 'confidence'."
)

_QUOTE_DESC = (
    "Get the current price snapshot for an Indian equity ticker. The ticker "
    "MUST end with .NS (NSE) or .BO (BSE). Returns price, day_change, "
    "day_change_pct, volume, week52_high, week52_low, fetched_at, and "
    "fresh_until. Responses are cached for 90 seconds — cite fetched_at when "
    "presenting price data to the user."
)

_HISTORICAL_DESC = (
    "Get OHLCV price bars for an Indian equity ticker. Ticker must end with "
    ".NS or .BO. 'period' accepts: 1d 5d 1mo 3mo 6mo 1y 2y 5y. "
    "'interval' accepts: 1m 5m 15m 1h 1d 1wk 1mo. Closes are split- and "
    "dividend-adjusted. Returns a 'bars' list of date/open/high/low/close/volume."
)


# ── Tool definitions ───────────────────────────────────────────────────────────


@tool(description=_RESOLVE_DESC)
async def resolve_asset_tool(query: str) -> str:
    """Resolve a company name or alias to NSE/BSE ticker candidates."""
    result = await asyncio.to_thread(resolve_asset, query)
    if not result.resolved:
        return json.dumps({"resolved": False, "candidates": [], "query": query})
    return result.model_dump_json()


@tool(description=_QUOTE_DESC)
async def get_quote_tool(ticker: str) -> str:
    """Get the current price snapshot for an NSE (.NS) or BSE (.BO) ticker."""
    ticker = ticker.upper()
    try:
        quote: MarketQuote = await asyncio.to_thread(_provider.get_quote, ticker)
        return quote.model_dump_json()
    except TickerNotFoundError as exc:
        raise ToolException(f"Ticker '{ticker}' not found on the exchange.") from exc
    except ProviderError as exc:
        raise ToolException(f"Market data unavailable: {exc}") from exc


@tool(description=_HISTORICAL_DESC)
async def get_historical_data_tool(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
) -> str:
    """Get OHLCV price bars for an NSE (.NS) or BSE (.BO) ticker."""
    ticker = ticker.upper()
    try:
        hist: HistoricalDataResponse = await asyncio.to_thread(
            _provider.get_historical, ticker, period, interval
        )
        # Return a concise summary rather than the full bars list to keep the
        # LLM context window manageable. The raw bars are available via the
        # /tools/historical-data endpoint if the UI needs to render them.
        if not hist.bars:
            raise ToolException(f"No historical data for '{ticker}'.")
 
        first = hist.bars[0]
        last = hist.bars[-1]
        pct_change = (
            round((last.close - first.open) / first.open * 100, 2)
            if first.open
            else None
        )
        return json.dumps(
            {
                "ticker": ticker,
                "period": period,
                "interval": interval,
                "bars_count": len(hist.bars),
                "from_date": str(first.date),
                "to_date": str(last.date),
                "open": first.open,
                "latest_close": last.close,
                "period_high": max(b.high for b in hist.bars),
                "period_low": min(b.low for b in hist.bars),
                "pct_change": pct_change,
                "adjusted": hist.adjusted,
                "fetched_at": hist.fetched_at.isoformat(),
            }
        )
    except TickerNotFoundError as exc:
        raise ToolException(f"Ticker '{ticker}' not found on the exchange.") from exc
    except ProviderError as exc:
        raise ToolException(f"Market data unavailable: {exc}") from exc


# Public list — imported by graph.py to bind to the agent.
get_quote_tool.handle_tool_error = True
get_historical_data_tool.handle_tool_error = True

MARKET_DATA_TOOLS = [resolve_asset_tool, get_quote_tool, get_historical_data_tool]
