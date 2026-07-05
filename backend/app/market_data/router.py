from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.market_data.cache import get_cached, make_params_hash, put_cache
from app.market_data.provider import (
    ProviderError,
    TickerNotFoundError,
    YFinanceProvider,
)
from app.market_data.resolver import resolve_asset
from app.market_data.schemas import AssetResolution, HistoricalDataResponse, MarketQuote

router = APIRouter(prefix="/tools", tags=["market-data"])

# Singleton provider — stateless, safe to share across requests.
_provider = YFinanceProvider()

# ── Validation sets ────────────────────────────────────────────────────────────

_VALID_RANGES = frozenset(
    {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
)
_VALID_INTERVALS = frozenset(
    {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "1q"}
)
_VALID_SUFFIXES = (".NS", ".BO")


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/resolve-asset", response_model=AssetResolution)
async def resolve_asset_endpoint(
    query: Annotated[str, Query(min_length=1, max_length=200)],
) -> AssetResolution:
    """Map a free-text company name or alias to NSE/BSE ticker candidates.

    Ambiguous queries (same company on multiple exchanges) always return both
    NSE and BSE candidates as separate items — the caller decides which to use.

    Example: GET /tools/resolve-asset?query=tata+motors
    """
    return await asyncio.to_thread(resolve_asset, query)


@router.get("/quote", response_model=MarketQuote)
async def quote_endpoint(
    ticker: Annotated[str, Query(min_length=1, max_length=40)],
    session: AsyncSession = Depends(get_session),
) -> MarketQuote:
    """Fetch the latest price snapshot for an NSE (.NS) or BSE (.BO) ticker.

    Responses are cached for 90 seconds. The is_stale flag is always False for
    live data; it becomes True when the cache layer serves an expired row while
    a background re-fetch is pending (reserved for future async refresh).

    Example: GET /tools/quote?ticker=INFY.NS
    """
    ticker = ticker.upper()
    _validate_indian_ticker(ticker)

    params_hash = make_params_hash(ticker, "quote")

    # ── Cache read (no transaction needed for SELECT) ──────────────────────────
    cached = await get_cached(session, "quote", params_hash)
    if cached is not None:
        return MarketQuote.model_validate(cached)

    # ── Live fetch (synchronous yfinance → thread pool) ────────────────────────
    quote = await _fetch_quote(ticker)

    # ── Cache write ────────────────────────────────────────────────────────────
    # session.begin() would fail here because get_cached's SELECT auto-began a
    # transaction. Flush + commit works regardless of whether one is open.
    await put_cache(
        session,
        snapshot_type="quote",
        params_hash=params_hash,
        ticker=ticker,
        payload=quote.model_dump(mode="json"),
        provider=quote.provider,
        fresh_until=quote.fresh_until,
    )
    await session.commit()

    return quote


@router.get("/historical-data", response_model=HistoricalDataResponse)
async def historical_data_endpoint(
    ticker: Annotated[str, Query(min_length=1, max_length=40)],
    range: Annotated[str, Query()] = "6mo",
    interval: Annotated[str, Query()] = "1d",
    session: AsyncSession = Depends(get_session),
) -> HistoricalDataResponse:
    """Fetch OHLCV bars for an NSE (.NS) or BSE (.BO) ticker.

    Closes are provider-adjusted (splits, dividends) — yfinance auto_adjust=True.

    Cache TTL: 90 seconds when the response contains today's open bar; 24 hours
    when all bars are from closed prior-day sessions (treated as immutable).

    Example: GET /tools/historical-data?ticker=INFY.NS&range=6mo&interval=1d
    """
    ticker = ticker.upper()
    _validate_indian_ticker(ticker)
    _validate_range(range)
    _validate_interval(interval)

    params_hash = make_params_hash(ticker, "historical", range=range, interval=interval)

    # ── Cache read ─────────────────────────────────────────────────────────────
    cached = await get_cached(session, "historical", params_hash)
    if cached is not None:
        return HistoricalDataResponse.model_validate(cached)

    # ── Live fetch ─────────────────────────────────────────────────────────────
    hist = await _fetch_historical(ticker, range, interval)

    # ── Cache write ────────────────────────────────────────────────────────────
    fresh_until = _historical_fresh_until(hist)
    await put_cache(
        session,
        snapshot_type="historical",
        params_hash=params_hash,
        ticker=ticker,
        payload=hist.model_dump(mode="json"),
        provider=hist.provider,
        fresh_until=fresh_until,
    )
    await session.commit()

    return hist


# ── Fetch helpers (wrap sync provider in thread pool) ─────────────────────────


async def _fetch_quote(ticker: str) -> MarketQuote:
    try:
        return await asyncio.to_thread(_provider.get_quote, ticker)
    except TickerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market data provider is temporarily unavailable.",
        ) from exc


async def _fetch_historical(
    ticker: str, period: str, interval: str
) -> HistoricalDataResponse:
    try:
        return await asyncio.to_thread(
            _provider.get_historical, ticker, period, interval
        )
    except TickerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market data provider is temporarily unavailable.",
        ) from exc


# ── Validation helpers ─────────────────────────────────────────────────────────


def _validate_indian_ticker(ticker: str) -> None:
    if not any(ticker.endswith(s) for s in _VALID_SUFFIXES):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Ticker '{ticker}' must end with .NS (NSE) or .BO (BSE). "
                "Use /tools/resolve-asset to find the canonical ticker for a company."
            ),
        )


def _validate_range(range_: str) -> None:
    if range_ not in _VALID_RANGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid range '{range_}'. Valid values: {sorted(_VALID_RANGES)}",
        )


def _validate_interval(interval: str) -> None:
    if interval not in _VALID_INTERVALS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Invalid interval '{interval}'. "
                f"Valid values: {sorted(_VALID_INTERVALS)}"
            ),
        )


# ── Cache TTL logic ────────────────────────────────────────────────────────────


def _historical_fresh_until(hist: HistoricalDataResponse) -> datetime:
    """90 s TTL if today's session bar is present; 24 h otherwise.

    Today's bar is 'open' in the sense that the close price may still change
    during the trading session. Prior-day bars are immutable once the session
    closes, so we use a generous 24 h TTL rather than 365 d to remain safe
    against rare events like split re-statements that yfinance may propagate.
    """
    now = datetime.now(timezone.utc)
    today = date.today()
    has_todays_bar = any(bar.date == today for bar in hist.bars)
    if has_todays_bar:
        return now + timedelta(seconds=YFinanceProvider.QUOTE_TTL_SECONDS)
    return now + timedelta(hours=24)
