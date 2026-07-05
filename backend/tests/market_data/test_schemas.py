from __future__ import annotations

from datetime import datetime, timezone

import pytest
from app.market_data.schemas import (
    Asset,
    AssetResolution,
    HistoricalBar,
    HistoricalDataResponse,
    MarketQuote,
)
from pydantic import ValidationError

# ── MarketQuote ────────────────────────────────────────────────────────────────


def _valid_quote(**overrides) -> dict:
    base = {
        "ticker": "INFY.NS",
        "exchange": "NSE",
        "price": 1500.0,
        "day_change": 12.5,
        "day_change_pct": 0.84,
        "volume": 3_000_000,
        "week52_high": 1800.0,
        "week52_low": 1200.0,
        "provider": "yfinance",
        "fetched_at": datetime.now(timezone.utc),
        "fresh_until": datetime.now(timezone.utc),
        "is_stale": False,
    }
    base.update(overrides)
    return base


def test_market_quote_valid():
    q = MarketQuote(**_valid_quote())
    assert q.ticker == "INFY.NS"
    assert q.exchange == "NSE"
    assert q.price == 1500.0
    assert q.is_stale is False


def test_market_quote_nullable_fields():
    q = MarketQuote(**_valid_quote(volume=None, week52_high=None, week52_low=None))
    assert q.volume is None
    assert q.week52_high is None
    assert q.week52_low is None


def test_market_quote_rejects_invalid_exchange():
    with pytest.raises(ValidationError):
        MarketQuote(**_valid_quote(exchange="NYSE"))


def test_market_quote_bse_exchange():
    q = MarketQuote(**_valid_quote(ticker="TATAMOTORS.BO", exchange="BSE"))
    assert q.exchange == "BSE"


# ── HistoricalBar ──────────────────────────────────────────────────────────────


def test_historical_bar_valid():
    from datetime import date

    bar = HistoricalBar(
        date=date(2024, 1, 15),
        open=1490.0,
        high=1510.0,
        low=1480.0,
        close=1500.0,
        volume=2_500_000,
    )
    assert bar.close == 1500.0


# ── HistoricalDataResponse ─────────────────────────────────────────────────────


def test_historical_data_response_empty_bars():
    h = HistoricalDataResponse(
        ticker="INFY.NS",
        range="6mo",
        interval="1d",
        bars=[],
        adjusted=True,
        provider="yfinance",
        fetched_at=datetime.now(timezone.utc),
    )
    assert h.bars == []
    assert h.adjusted is True


# ── Asset ──────────────────────────────────────────────────────────────────────


def test_asset_valid_nse():
    a = Asset(
        canonical_ticker="INFY.NS",
        exchange="NSE",
        name="Infosys Limited",
        asset_class="equity",
        confidence=0.95,
    )
    assert a.currency == "INR"  # default
    assert a.confidence == 0.95


def test_asset_rejects_invalid_exchange():
    with pytest.raises(ValidationError):
        Asset(
            canonical_ticker="INFY.NS",
            exchange="NASDAQ",
            name="Infosys",
            asset_class="equity",
            confidence=0.5,
        )


def test_asset_confidence_bounds():
    with pytest.raises(ValidationError):
        Asset(
            canonical_ticker="INFY.NS",
            exchange="NSE",
            name="Infosys",
            asset_class="equity",
            confidence=1.5,  # > 1.0 — should fail
        )
    with pytest.raises(ValidationError):
        Asset(
            canonical_ticker="INFY.NS",
            exchange="NSE",
            name="Infosys",
            asset_class="equity",
            confidence=-0.1,  # < 0.0 — should fail
        )


# ── AssetResolution ────────────────────────────────────────────────────────────


def test_asset_resolution_resolved():
    r = AssetResolution(
        query="infosys",
        resolved=True,
        candidates=[
            Asset(
                canonical_ticker="INFY.NS",
                exchange="NSE",
                name="Infosys Limited",
                asset_class="equity",
                confidence=1.0,
            )
        ],
    )
    assert r.resolved is True
    assert len(r.candidates) == 1


def test_asset_resolution_unresolved():
    r = AssetResolution(query="zerodha", resolved=False, candidates=[])
    assert r.resolved is False
    assert r.candidates == []
