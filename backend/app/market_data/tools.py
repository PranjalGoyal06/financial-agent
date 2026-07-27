from __future__ import annotations

import asyncio
import json

from langchain_core.tools import ToolException, tool

from app.market_data.provider import (
    ProviderError,
    TickerNotFoundError,
    YFinanceProvider,
)
from app.market_data.resolver import resolve_asset
from app.market_data.schemas import HistoricalDataResponse, MarketQuote
from app.db import AsyncSessionLocal
from app.models import InstrumentModel
from sqlalchemy import select

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


_FUND_DESC = (
    "Get fundamental financial metrics for an Indian equity ticker. The ticker "
    "MUST end with .NS (NSE) or .BO (BSE). Returns valuation ratios (P/E, P/B, P/S, PEG), "
    "operating margins, return on equity (ROE), revenue/earnings growth, and analyst targets. "
    "Ratios may be None if not available on yfinance — treat None as unavailable, do not invent values."
)


@tool(description=_FUND_DESC)
async def get_fundamentals_tool(ticker: str) -> str:
    """Get key fundamental metrics (valuation, margins, growth) for an equity ticker."""
    ticker = ticker.upper()
    try:
        fund = await asyncio.to_thread(_provider.get_fundamentals, ticker)
        return fund.model_dump_json()
    except TickerNotFoundError as exc:
        raise ToolException(f"Ticker '{ticker}' not found on the exchange.") from exc
    except ProviderError as exc:
        raise ToolException(f"Fundamentals data unavailable: {exc}") from exc


_META_DESC = (
    "Get rich static metadata for an Indian equity ticker from the local database. "
    "The ticker MUST end with .NS (NSE) or .BO (BSE). Returns sector, industry, "
    "market cap bucket, company name, summary, website, and employee count. "
    "Use this tool when you need basic context about a company or what it does."
)

@tool(description=_META_DESC)
async def get_instrument_metadata_tool(ticker: str) -> str:
    """Get rich static metadata (sector, industry, summary) for a ticker."""
    ticker = ticker.upper()
    async with AsyncSessionLocal() as session:
        stmt = select(InstrumentModel).where(InstrumentModel.ticker == ticker)
        res = await session.execute(stmt)
        instrument = res.scalar_one_or_none()
        
        if not instrument:
            raise ToolException(f"Metadata for ticker '{ticker}' not found in the local database.")
            
        return json.dumps({
            "ticker": instrument.ticker,
            "display_name": instrument.display_name,
            "company_name": instrument.company_name,
            "sector": instrument.sector,
            "industry": instrument.industry,
            "market_cap": instrument.market_cap,
            "market_cap_bucket": instrument.market_cap_bucket,
            "country": instrument.country,
            "website": instrument.website,
            "full_time_employees": instrument.full_time_employees,
            "summary": instrument.summary,
        })


# Public list — imported by graph.py to bind to the agent.
get_quote_tool.handle_tool_error = True
get_historical_data_tool.handle_tool_error = True
get_fundamentals_tool.handle_tool_error = True
get_instrument_metadata_tool.handle_tool_error = True

MARKET_DATA_TOOLS = [
    resolve_asset_tool,
    get_quote_tool,
    get_historical_data_tool,
    get_fundamentals_tool,
    get_instrument_metadata_tool,
]

