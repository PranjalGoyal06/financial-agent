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


class FundamentalsSnapshot(BaseModel):
    """Fundamental metrics for a single Indian equity ticker.

    Layer 1 (Raw fetch) — sourced from yfinance ``.info`` dict.

    All metric fields are ``float | None``.  yfinance coverage for NSE/BSE
    tickers is directional, not forensic-grade: fields are frequently missing,
    stale, or only partially populated.  **Never invent a value for a None
    field** — surface the None to the synthesis prompt as "not available".

    Field → yfinance .info key mapping
    ───────────────────────────────────
    pe_ratio              trailingPE
    pb_ratio              priceToBook
    ps_ratio              priceToSalesTrailing12Months
    peg_ratio             pegRatio
    enterprise_value      enterpriseValue
    eps_ttm               trailingEps
    eps_forward           forwardEps
    book_value_per_share  bookValue
    profit_margin         profitMargins
    operating_margin      operatingMargins
    return_on_equity      returnOnEquity
    return_on_assets      returnOnAssets
    dividend_yield        dividendYield  (decimal, e.g. 0.012 = 1.2%)
    payout_ratio          payoutRatio
    market_cap            marketCap
    shares_outstanding    sharesOutstanding
    revenue_ttm           totalRevenue
    revenue_growth        revenueGrowth  (yoy, decimal)
    earnings_growth       earningsGrowth (yoy, decimal)
    analyst_target_price  targetMeanPrice
    """

    ticker: str
    exchange: Literal["NSE", "BSE"]

    # Valuation
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    peg_ratio: float | None = None
    enterprise_value: float | None = None

    # Per-share
    eps_ttm: float | None = None
    eps_forward: float | None = None
    book_value_per_share: float | None = None

    # Profitability
    profit_margin: float | None = None
    operating_margin: float | None = None
    return_on_equity: float | None = None
    return_on_assets: float | None = None

    # Dividends
    dividend_yield: float | None = None
    payout_ratio: float | None = None

    # Size
    market_cap: float | None = None
    shares_outstanding: float | None = None

    # Revenue / growth
    revenue_ttm: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None

    # Analyst consensus
    analyst_target_price: float | None = None

    provider: str
    fetched_at: datetime

