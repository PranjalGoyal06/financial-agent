from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from app.db import AsyncSessionLocal, init_db
from app.market_data.cache import get_cached, make_params_hash, put_cache
from app.models import MarketSnapshotModel
from sqlalchemy import delete


# ── make_params_hash tests ───────────────────────────────────────────────────


def test_hash_is_deterministic():
    h1 = make_params_hash("INFY.NS", "quote")
    h2 = make_params_hash("INFY.NS", "quote")
    assert h1 == h2


def test_hash_differs_by_ticker():
    h1 = make_params_hash("INFY.NS", "quote")
    h2 = make_params_hash("TCS.NS", "quote")
    assert h1 != h2


def test_hash_differs_by_snapshot_type():
    h1 = make_params_hash("INFY.NS", "quote")
    h2 = make_params_hash("INFY.NS", "historical")
    assert h1 != h2


def test_hash_differs_by_range():
    h1 = make_params_hash("INFY.NS", "historical", range="6mo", interval="1d")
    h2 = make_params_hash("INFY.NS", "historical", range="1y", interval="1d")
    assert h1 != h2


def test_hash_differs_by_interval():
    h1 = make_params_hash("INFY.NS", "historical", range="6mo", interval="1d")
    h2 = make_params_hash("INFY.NS", "historical", range="6mo", interval="1wk")
    assert h1 != h2


def test_hash_kwarg_order_independent():
    """Kwargs should be sorted so key order never changes the hash."""
    h1 = make_params_hash("INFY.NS", "historical", range="6mo", interval="1d")
    h2 = make_params_hash("INFY.NS", "historical", interval="1d", range="6mo")
    assert h1 == h2


def test_hash_is_64_hex_chars():
    h = make_params_hash("INFY.NS", "quote")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# ── Database Cache tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_put_and_get_cached_flow() -> None:
    """Verify that put_cache stores the payload and get_cached retrieves it if fresh."""
    await init_db()

    ticker = "INFY.NS"
    snapshot_type = "quote"
    params_hash = make_params_hash(ticker, snapshot_type)
    payload = {"price": 1500.0, "currency": "INR"}
    provider = "yfinance"

    # Future expiration: should hit the cache
    fresh_until = datetime.now(timezone.utc) + timedelta(seconds=30)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(delete(MarketSnapshotModel))
            await put_cache(
                session,
                snapshot_type=snapshot_type,
                params_hash=params_hash,
                ticker=ticker,
                payload=payload,
                provider=provider,
                fresh_until=fresh_until,
            )

        # Retrieve and verify cached
        cached = await get_cached(session, snapshot_type, params_hash)
        assert cached == payload


@pytest.mark.asyncio
async def test_get_cached_expired_returns_none() -> None:
    """Verify that get_cached returns None if the entry has expired."""
    await init_db()

    ticker = "INFY.NS"
    snapshot_type = "quote"
    params_hash = make_params_hash(ticker, snapshot_type)
    payload = {"price": 1500.0, "currency": "INR"}
    provider = "yfinance"

    # Past expiration: should expire and return None
    fresh_until = datetime.now(timezone.utc) - timedelta(seconds=1)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(delete(MarketSnapshotModel))
            await put_cache(
                session,
                snapshot_type=snapshot_type,
                params_hash=params_hash,
                ticker=ticker,
                payload=payload,
                provider=provider,
                fresh_until=fresh_until,
            )

        # Retrieve and verify it is not returned (considered expired)
        cached = await get_cached(session, snapshot_type, params_hash)
        assert cached is None
