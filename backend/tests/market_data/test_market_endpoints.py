from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from app.market_data.provider import TickerNotFoundError, YFinanceProvider
from app.market_data.schemas import (
    Asset,
    AssetResolution,
    HistoricalBar,
    HistoricalDataResponse,
    MarketQuote,
)
from fastapi.testclient import TestClient

# ── Stub factories ─────────────────────────────────────────────────────────────


def _stub_quote(ticker: str = "INFY.NS") -> MarketQuote:
    now = datetime.now(timezone.utc)
    return MarketQuote(
        ticker=ticker,
        exchange="NSE",
        price=1500.0,
        day_change=12.5,
        day_change_pct=0.84,
        volume=3_000_000,
        week52_high=1800.0,
        week52_low=1200.0,
        provider="yfinance",
        fetched_at=now,
        fresh_until=now + timedelta(seconds=90),
        is_stale=False,
    )


def _stub_hist(ticker: str = "INFY.NS") -> HistoricalDataResponse:
    return HistoricalDataResponse(
        ticker=ticker,
        range="6mo",
        interval="1d",
        bars=[
            HistoricalBar(
                date=date(2024, 1, 15),
                open=1490.0,
                high=1510.0,
                low=1480.0,
                close=1500.0,
                volume=2_500_000,
            )
        ],
        adjusted=True,
        provider="yfinance",
        fetched_at=datetime.now(timezone.utc),
    )


def _stub_resolution(query: str = "infosys") -> AssetResolution:
    return AssetResolution(
        query=query,
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


# ── /tools/resolve-asset ───────────────────────────────────────────────────────


def test_resolve_asset_returns_200(client: TestClient) -> None:
    """Verify successful asset resolution mapping."""
    with patch(
        "app.market_data.router.resolve_asset", return_value=_stub_resolution()
    ):
        response = client.get("/tools/resolve-asset?query=infosys")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resolved"] is True
    assert payload["candidates"][0]["canonical_ticker"] == "INFY.NS"
    assert payload["candidates"][0]["exchange"] == "NSE"


def test_resolve_asset_missing_query(client: TestClient) -> None:
    """Verify that a missing query parameter triggers validation failure (422)."""
    response = client.get("/tools/resolve-asset")
    assert response.status_code == 422


def test_resolve_asset_unresolved(client: TestClient) -> None:
    """Verify that a query with no matches returns unresolved candidate list."""
    unresolved = AssetResolution(query="zerodha", resolved=False, candidates=[])
    with patch("app.market_data.router.resolve_asset", return_value=unresolved):
        response = client.get("/tools/resolve-asset?query=zerodha")

    assert response.status_code == 200
    assert response.json()["resolved"] is False
    assert response.json()["candidates"] == []


# ── /tools/quote ──────────────────────────────────────────────────────────────


def test_quote_returns_200(client: TestClient) -> None:
    """Verify fetching quote snapshot for a valid ticker returns 200."""
    with patch.object(YFinanceProvider, "get_quote", return_value=_stub_quote()):
        response = client.get("/tools/quote?ticker=INFY.NS")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "INFY.NS"
    assert payload["exchange"] == "NSE"
    assert payload["price"] == 1500.0
    assert payload["provider"] == "yfinance"


def test_quote_rejects_non_indian_ticker(client: TestClient) -> None:
    """Verify that non-Indian tickers (e.g. without NS or BO) return validation error (422)."""
    response = client.get("/tools/quote?ticker=AAPL")
    assert response.status_code == 422
    assert ".NS" in response.json()["detail"] or ".BO" in response.json()["detail"]


def test_quote_returns_404_for_unknown_ticker(client: TestClient) -> None:
    """Verify that a validly-suffixed but non-existent ticker returns 404."""
    with patch.object(
        YFinanceProvider,
        "get_quote",
        side_effect=TickerNotFoundError("FAKE999.NS"),
    ):
        response = client.get("/tools/quote?ticker=FAKE999.NS")

    assert response.status_code == 404
    assert "FAKE999.NS" in response.json()["detail"]


def test_quote_is_served_from_cache_on_second_call(client: TestClient) -> None:
    """Verify that fetching quote twice within TTL reads from database cache."""
    stub = _stub_quote()
    call_count = 0

    def counting_get_quote(ticker: str) -> MarketQuote:
        nonlocal call_count
        call_count += 1
        return stub

    with patch.object(YFinanceProvider, "get_quote", side_effect=counting_get_quote):
        r1 = client.get("/tools/quote?ticker=INFY.NS")
        r2 = client.get("/tools/quote?ticker=INFY.NS")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert call_count == 1
    assert r1.json()["fetched_at"] == r2.json()["fetched_at"]


def test_quote_ticker_is_uppercased(client: TestClient) -> None:
    """Verify that lowercased tickers are converted to uppercase before querying the provider."""
    with patch.object(
        YFinanceProvider, "get_quote", return_value=_stub_quote()
    ) as mock:
        client.get("/tools/quote?ticker=infy.ns")
    mock.assert_called_once_with("INFY.NS")


# ── /tools/historical-data ────────────────────────────────────────────────────


def test_historical_data_returns_200(client: TestClient) -> None:
    """Verify historical data fetching endpoint works with valid params."""
    with patch.object(
        YFinanceProvider, "get_historical", return_value=_stub_hist()
    ):
        response = client.get(
            "/tools/historical-data?ticker=INFY.NS&range=6mo&interval=1d"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "INFY.NS"
    assert payload["adjusted"] is True
    assert len(payload["bars"]) == 1
    assert payload["bars"][0]["close"] == 1500.0


def test_historical_data_defaults_applied(client: TestClient) -> None:
    """Verify that default period (6mo) and interval (1d) are applied if omitted."""
    with patch.object(
        YFinanceProvider, "get_historical", return_value=_stub_hist()
    ) as mock:
        client.get("/tools/historical-data?ticker=INFY.NS")
    mock.assert_called_once_with("INFY.NS", "6mo", "1d")


def test_historical_data_rejects_invalid_range(client: TestClient) -> None:
    """Verify that an unsupported range value returns 422."""
    response = client.get(
        "/tools/historical-data?ticker=INFY.NS&range=99y&interval=1d"
    )
    assert response.status_code == 422
    assert "range" in response.json()["detail"].lower()


def test_historical_data_rejects_invalid_interval(client: TestClient) -> None:
    """Verify that an unsupported interval value returns 422."""
    response = client.get(
        "/tools/historical-data?ticker=INFY.NS&range=6mo&interval=3d"
    )
    assert response.status_code == 422
    assert "interval" in response.json()["detail"].lower()


def test_historical_data_rejects_non_indian_ticker(client: TestClient) -> None:
    """Verify that non-Indian tickers are rejected with 422 for historical data query."""
    response = client.get("/tools/historical-data?ticker=AAPL&range=6mo&interval=1d")
    assert response.status_code == 422


def test_historical_data_404_for_unknown_ticker(client: TestClient) -> None:
    """Verify that unknown tickers return 404 for historical data query."""
    with patch.object(
        YFinanceProvider,
        "get_historical",
        side_effect=TickerNotFoundError("FAKE999.NS"),
    ):
        response = client.get(
            "/tools/historical-data?ticker=FAKE999.NS&range=6mo&interval=1d"
        )

    assert response.status_code == 404


def test_historical_data_cached_on_second_call(client: TestClient) -> None:
    """Verify that historical data requests are cached correctly."""
    stub = _stub_hist()
    call_count = 0

    def counting_get_historical(
        ticker: str, period: str, interval: str
    ) -> HistoricalDataResponse:
        nonlocal call_count
        call_count += 1
        return stub

    with patch.object(
        YFinanceProvider, "get_historical", side_effect=counting_get_historical
    ):
        r1 = client.get("/tools/historical-data?ticker=INFY.NS&range=6mo&interval=1d")
        r2 = client.get("/tools/historical-data?ticker=INFY.NS&range=6mo&interval=1d")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert call_count == 1
