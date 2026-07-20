from __future__ import annotations

import asyncio
import json

from langchain_core.tools import ToolException, tool

from app.market_data.provider import (
    ProviderError,
    TickerNotFoundError,
    YFinanceProvider,
)
from app.ta.lib import compute_ema, compute_rsi, compute_sma

_provider = YFinanceProvider()


@tool
async def compute_sma_tool(ticker: str, window: int = 50, period: str = "1y", interval: str = "1d") -> str:
    """Compute Simple Moving Average (SMA) for a ticker. Returns the latest value."""
    ticker = ticker.upper()
    try:
        hist = await asyncio.to_thread(_provider.get_historical, ticker, period, interval)
        if not hist.bars:
            raise ToolException(f"No price bars found for '{ticker}'.")
        
        sma = compute_sma(hist.bars, window)
        latest_sma = next((v for v in reversed(sma) if v is not None), None)
        
        return json.dumps({
            "ticker": ticker,
            "indicator": f"SMA_{window}",
            "latest_value": latest_sma,
        })
    except (TickerNotFoundError, ProviderError) as exc:
        raise ToolException(f"Data fetch failed: {exc}") from exc


@tool
async def compute_ema_tool(ticker: str, window: int = 20, period: str = "1y", interval: str = "1d") -> str:
    """Compute Exponential Moving Average (EMA) for a ticker. Returns the latest value."""
    ticker = ticker.upper()
    try:
        hist = await asyncio.to_thread(_provider.get_historical, ticker, period, interval)
        if not hist.bars:
            raise ToolException(f"No price bars found for '{ticker}'.")
        
        ema = compute_ema(hist.bars, window)
        latest_ema = next((v for v in reversed(ema) if v is not None), None)
        
        return json.dumps({
            "ticker": ticker,
            "indicator": f"EMA_{window}",
            "latest_value": latest_ema,
        })
    except (TickerNotFoundError, ProviderError) as exc:
        raise ToolException(f"Data fetch failed: {exc}") from exc


@tool
async def compute_rsi_tool(ticker: str, window: int = 14, period: str = "1y", interval: str = "1d") -> str:
    """Compute Relative Strength Index (RSI) for a ticker. Returns the latest value."""
    ticker = ticker.upper()
    try:
        hist = await asyncio.to_thread(_provider.get_historical, ticker, period, interval)
        if not hist.bars:
            raise ToolException(f"No price bars found for '{ticker}'.")
        
        rsi = compute_rsi(hist.bars, window)
        latest_rsi = next((v for v in reversed(rsi) if v is not None), None)
        
        return json.dumps({
            "ticker": ticker,
            "indicator": f"RSI_{window}",
            "latest_value": latest_rsi,
        })
    except (TickerNotFoundError, ProviderError) as exc:
        raise ToolException(f"Data fetch failed: {exc}") from exc
