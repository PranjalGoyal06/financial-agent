from __future__ import annotations

import asyncio
import json

from langchain_core.tools import ToolException, tool

from app.market_data.provider import (
    ProviderError,
    TickerNotFoundError,
    YFinanceProvider,
)
from app.quant.lib import (
    compute_52w_distance,
    compute_max_drawdown,
    compute_returns,
    compute_sharpe_ratio,
    compute_volatility,
)

_provider = YFinanceProvider()


@tool
async def compute_returns_tool(ticker: str, period: str = "1y", interval: str = "1d") -> str:
    """Compute simple, CAGR, and log returns for a ticker price series."""
    ticker = ticker.upper()
    try:
        hist = await asyncio.to_thread(_provider.get_historical, ticker, period, interval)
        if not hist.bars:
            raise ToolException(f"No price bars found for '{ticker}'.")
        
        simple = compute_returns(hist.bars, method="simple")
        cagr = compute_returns(hist.bars, method="cagr")
        
        return json.dumps({
            "ticker": ticker,
            "period": period,
            "simple_return": simple,
            "cagr": cagr,
        })
    except (TickerNotFoundError, ProviderError) as exc:
        raise ToolException(f"Data fetch failed: {exc}") from exc


@tool
async def compute_volatility_tool(ticker: str, period: str = "1y", interval: str = "1d") -> str:
    """Compute annualised historical volatility for a ticker price series."""
    ticker = ticker.upper()
    try:
        hist = await asyncio.to_thread(_provider.get_historical, ticker, period, interval)
        if not hist.bars:
            raise ToolException(f"No price bars found for '{ticker}'.")
        
        vol = compute_volatility(hist.bars)
        return json.dumps({
            "ticker": ticker,
            "period": period,
            "volatility_annualized": vol,
        })
    except (TickerNotFoundError, ProviderError) as exc:
        raise ToolException(f"Data fetch failed: {exc}") from exc


@tool
async def compute_max_drawdown_tool(ticker: str, period: str = "1y", interval: str = "1d") -> str:
    """Compute maximum peak-to-trough drawdown for a ticker price series."""
    ticker = ticker.upper()
    try:
        hist = await asyncio.to_thread(_provider.get_historical, ticker, period, interval)
        if not hist.bars:
            raise ToolException(f"No price bars found for '{ticker}'.")
        
        dd, peak_dt, trough_dt = compute_max_drawdown(hist.bars)
        return json.dumps({
            "ticker": ticker,
            "period": period,
            "max_drawdown": dd,
            "peak_date": str(peak_dt),
            "trough_date": str(trough_dt),
        })
    except (TickerNotFoundError, ProviderError) as exc:
        raise ToolException(f"Data fetch failed: {exc}") from exc


@tool
async def compute_sharpe_ratio_tool(
    ticker: str, period: str = "1y", interval: str = "1d", risk_free_rate: float = 0.065
) -> str:
    """Compute annualised Sharpe ratio for a ticker price series."""
    ticker = ticker.upper()
    try:
        hist = await asyncio.to_thread(_provider.get_historical, ticker, period, interval)
        if not hist.bars:
            raise ToolException(f"No price bars found for '{ticker}'.")
        
        sharpe = compute_sharpe_ratio(hist.bars, risk_free_rate=risk_free_rate)
        return json.dumps({
            "ticker": ticker,
            "period": period,
            "sharpe_ratio": sharpe,
            "risk_free_rate": risk_free_rate,
        })
    except (TickerNotFoundError, ProviderError) as exc:
        raise ToolException(f"Data fetch failed: {exc}") from exc


@tool
async def compute_52w_distance_tool(ticker: str) -> str:
    """Compute distance of current price from its 52-week high and low."""
    ticker = ticker.upper()
    try:
        hist = await asyncio.to_thread(_provider.get_historical, ticker, "1y", "1d")
        if not hist.bars:
            raise ToolException(f"No price bars found for '{ticker}'.")
        
        dist = compute_52w_distance(hist.bars)
        return json.dumps({
            "ticker": ticker,
            "pct_from_high": dist["pct_from_high"],
            "pct_from_low": dist["pct_from_low"],
            "high_52w": dist["high_52w"],
            "low_52w": dist["low_52w"],
        })
    except (TickerNotFoundError, ProviderError) as exc:
        raise ToolException(f"Data fetch failed: {exc}") from exc
