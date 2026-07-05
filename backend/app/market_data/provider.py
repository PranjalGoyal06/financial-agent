from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Protocol

import yfinance as yf

from app.market_data.schemas import (
    HistoricalBar,
    HistoricalDataResponse,
    MarketQuote,
)

# ── Suffix → exchange mapping ──────────────────────────────────────────────────

_SUFFIX_TO_EXCHANGE: dict[str, Literal["NSE", "BSE"]] = {
    ".NS": "NSE",
    ".BO": "BSE",
}


def exchange_from_ticker(ticker: str) -> Literal["NSE", "BSE"]:
    upper = ticker.upper()
    for suffix, exchange in _SUFFIX_TO_EXCHANGE.items():
        if upper.endswith(suffix):
            return exchange
    return "NSE"  # safe default; router validates suffix before reaching here


# ── Custom exceptions ──────────────────────────────────────────────────────────


class TickerNotFoundError(Exception):
    """Raised when the provider cannot locate price data for the given ticker."""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        super().__init__(f"Ticker '{ticker}' not found.")


class ProviderError(Exception):
    """Raised for transient upstream failures (network, timeout, parse error)."""


# ── Provider Protocol ──────────────────────────────────────────────────────────


class MarketDataProvider(Protocol):
    """Structural interface for market data providers.

    Implementations are synchronous (run via asyncio.to_thread in the router).
    Swapping to Kite Connect or Upstox only requires a new class that satisfies
    this protocol — no changes to cache, resolver, or router.
    """

    def get_quote(self, ticker: str) -> MarketQuote: ...

    def get_historical(
        self, ticker: str, period: str, interval: str
    ) -> HistoricalDataResponse: ...


# ── yfinance field mappings ────────────────────────────────────────────────────
#
#   MarketQuote field         yfinance info key
#   ─────────────────────     ───────────────────────────────────
#   price                     currentPrice → regularMarketPrice
#   day_change                regularMarketChange
#   day_change_pct            regularMarketChangePercent
#   volume                    regularMarketVolume
#   week52_high               fiftyTwoWeekHigh
#   week52_low                fiftyTwoWeekLow


class YFinanceProvider:
    """yfinance-backed implementation of MarketDataProvider.

    All network I/O is synchronous; callers must offload to a thread pool
    (asyncio.to_thread) rather than calling directly from async context.

    Provider name is exposed in every response payload to support the
    'Provider: yfinance (unofficial)' freshness label in the UI.
    """

    PROVIDER_NAME = "yfinance"
    QUOTE_TTL_SECONDS: int = 90  # midpoint of the 60–120 s window

    def get_quote(self, ticker: str) -> MarketQuote:
        try:
            info: dict = yf.Ticker(ticker).info
        except Exception as exc:
            raise ProviderError(f"yfinance request failed for '{ticker}'.") from exc

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            raise TickerNotFoundError(ticker)

        now = datetime.now(timezone.utc)
        return MarketQuote(
            ticker=ticker,
            exchange=exchange_from_ticker(ticker),
            price=float(price),
            day_change=float(info.get("regularMarketChange") or 0.0),
            day_change_pct=float(info.get("regularMarketChangePercent") or 0.0),
            volume=info.get("regularMarketVolume"),
            week52_high=_optional_float(info.get("fiftyTwoWeekHigh")),
            week52_low=_optional_float(info.get("fiftyTwoWeekLow")),
            provider=self.PROVIDER_NAME,
            fetched_at=now,
            fresh_until=now + timedelta(seconds=self.QUOTE_TTL_SECONDS),
            is_stale=False,
        )

    def get_historical(
        self, ticker: str, period: str, interval: str
    ) -> HistoricalDataResponse:
        try:
            df = yf.Ticker(ticker).history(
                period=period, interval=interval, auto_adjust=True
            )
        except Exception as exc:
            raise ProviderError(f"yfinance request failed for '{ticker}'.") from exc

        if df is None or df.empty:
            raise TickerNotFoundError(ticker)

        df = df.reset_index()
        bars: list[HistoricalBar] = []
        for _, row in df.iterrows():
            dt = row["Datetime"] if "Datetime" in df.columns else row["Date"]
            bar_date = dt.date() if hasattr(dt, "date") else dt
            bars.append(
                HistoricalBar(
                    date=bar_date,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                )
            )

        return HistoricalDataResponse(
            ticker=ticker,
            range=period,
            interval=interval,
            bars=bars,
            adjusted=True,  # yfinance auto_adjust=True always
            provider=self.PROVIDER_NAME,
            fetched_at=datetime.now(timezone.utc),
        )


# ── Helpers ────────────────────────────────────────────────────────────────────


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
