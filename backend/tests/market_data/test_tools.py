from __future__ import annotations

import json
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from app.market_data.provider import TickerNotFoundError
from app.market_data.schemas import (
    Asset,
    AssetResolution,
    HistoricalBar,
    HistoricalDataResponse,
    MarketQuote,
)
from app.market_data.tools import (
    get_historical_data_tool,
    get_quote_tool,
    resolve_asset_tool,
)

# ── Stub factories ─────────────────────────────────────────────────────────────


def _stub_quote(ticker: str = "INFY.NS") -> MarketQuote:
    now = datetime.now(timezone.utc)
    return MarketQuote(
        ticker=ticker,
        exchange="NSE",
        price=1523.5,
        day_change=12.5,
        day_change_pct=0.84,
        volume=3_000_000,
        week52_high=1800.0,
        week52_low=1200.0,
        provider="yfinance",
        fetched_at=now,
        fresh_until=now,
        is_stale=False,
    )


def _stub_hist(ticker: str = "INFY.NS") -> HistoricalDataResponse:
    return HistoricalDataResponse(
        ticker=ticker,
        range="6mo",
        interval="1d",
        bars=[
            HistoricalBar(
                date=date(2024, 1, 1),
                open=1400.0,
                high=1800.0,
                low=1200.0,
                close=1600.0,
                volume=1_000_000,
            )
        ],
        adjusted=True,
        provider="yfinance",
        fetched_at=datetime.now(timezone.utc),
    )


def _stub_resolution() -> AssetResolution:
    return AssetResolution(
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


# ── resolve_asset_tool ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_asset_tool_returns_json() -> None:
    with patch(
        "app.market_data.tools.resolve_asset", return_value=_stub_resolution()
    ):
        result = await resolve_asset_tool.ainvoke({"query": "infosys"})

    parsed = json.loads(result)
    assert parsed["resolved"] is True
    assert parsed["candidates"][0]["canonical_ticker"] == "INFY.NS"


@pytest.mark.asyncio
async def test_resolve_asset_tool_unresolved_returns_json() -> None:
    with patch(
        "app.market_data.tools.resolve_asset",
        return_value=AssetResolution(query="zerodha", resolved=False, candidates=[]),
    ):
        result = await resolve_asset_tool.ainvoke({"query": "zerodha"})

    parsed = json.loads(result)
    assert parsed["resolved"] is False
    assert parsed["candidates"] == []


# ── get_quote_tool ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_quote_tool_returns_json() -> None:
    from app.market_data.tools import _provider

    with patch.object(_provider, "get_quote", return_value=_stub_quote()):
        result = await get_quote_tool.ainvoke({"ticker": "infy.ns"})  # lowercase input

    parsed = json.loads(result)
    assert parsed["ticker"] == "INFY.NS"  # must be uppercased
    assert parsed["price"] == 1523.5
    assert parsed["exchange"] == "NSE"


@pytest.mark.asyncio
async def test_get_quote_tool_not_found_returns_error_json() -> None:
    from app.market_data.tools import _provider

    with patch.object(
        _provider, "get_quote", side_effect=TickerNotFoundError("FAKE.NS")
    ):
        result = await get_quote_tool.ainvoke({"ticker": "FAKE.NS"})

    assert "FAKE.NS" in result
    assert "not found" in result


# ── get_historical_data_tool ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_historical_data_tool_returns_summary_json() -> None:
    from app.market_data.tools import _provider

    with patch.object(_provider, "get_historical", return_value=_stub_hist()):
        result = await get_historical_data_tool.ainvoke(
            {"ticker": "INFY.NS", "period": "6mo", "interval": "1d"}
        )

    parsed = json.loads(result)
    assert parsed["ticker"] == "INFY.NS"
    assert parsed["bars_count"] == 1
    assert "pct_change" in parsed
    assert "latest_close" in parsed


@pytest.mark.asyncio
async def test_get_historical_data_tool_not_found_returns_error_json() -> None:
    from app.market_data.tools import _provider

    with patch.object(
        _provider, "get_historical", side_effect=TickerNotFoundError("FAKE.NS")
    ):
        result = await get_historical_data_tool.ainvoke(
            {"ticker": "FAKE.NS", "period": "6mo", "interval": "1d"}
        )

    assert "FAKE.NS" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_get_historical_data_tool_defaults() -> None:
    """Omitting period and interval should use 6mo/1d defaults."""
    from app.market_data.tools import _provider

    with patch.object(_provider, "get_historical", return_value=_stub_hist()) as mock:
        await get_historical_data_tool.ainvoke({"ticker": "INFY.NS"})

    mock.assert_called_once_with("INFY.NS", "6mo", "1d")
