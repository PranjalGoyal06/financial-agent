from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class MarketQuote(BaseModel):
    """Live or recently-cached price snapshot for a single Indian equity ticker.

    Layer 1 (Raw fetch) — output suitable for direct citation.
    market_cap is intentionally absent; compute it as price × shares_outstanding
    at the aggregation layer (Layer 2) to keep this schema a pure data carrier.
    """

    ticker: str
    exchange: Literal["NSE", "BSE"]
    price: float
    day_change: float
    day_change_pct: float
    volume: int | None
    week52_high: float | None
    week52_low: float | None
    provider: str
    fetched_at: datetime
    fresh_until: datetime
    is_stale: bool


class HistoricalBar(BaseModel):
    """Single OHLCV bar. Closes are provider-adjusted (splits, dividends)."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class HistoricalDataResponse(BaseModel):
    """OHLCV series for a ticker.

    Layer 1 (Raw fetch) — adjusted=True always for yfinance; field exists so a
    future provider can signal unadjusted closes without changing callers.
    """

    ticker: str
    range: str
    interval: str
    bars: list[HistoricalBar]
    adjusted: bool
    provider: str
    fetched_at: datetime


class Asset(BaseModel):
    """A single resolved ticker candidate.

    confidence is a 0.0–1.0 match score against the original free-text query.
    Multiple Assets with the same underlying company but different exchanges are
    always returned separately — never collapsed.
    """

    canonical_ticker: str
    exchange: Literal["NSE", "BSE"]
    name: str
    asset_class: str
    currency: str = "INR"
    confidence: float = Field(ge=0.0, le=1.0)


class AssetResolution(BaseModel):
    """Result of a free-text → ticker resolution request.

    Layer 1 (Raw fetch) — pure deterministic mapping, no LLM involvement.
    resolved=False means no NSE/BSE candidates were found; candidates is empty.
    """

    query: str
    resolved: bool
    candidates: list[Asset]
