from __future__ import annotations

import pytest
from app.db.repositories.artifacts_repository import DEFAULT_ARTIFACTS_REPOSITORY
from app.db.repositories.chat_repository import DEFAULT_CHAT_REPOSITORY
from app.db.repositories.holdings_repository import DEFAULT_HOLDINGS_REPOSITORY
from app.main import app
from app.services.market_data_service import MarketDataEnvelope
from app.services.portfolio_service import DEFAULT_PORTFOLIO_SERVICE
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_in_memory_repositories() -> None:
    DEFAULT_HOLDINGS_REPOSITORY.clear()
    DEFAULT_ARTIFACTS_REPOSITORY.clear()
    DEFAULT_CHAT_REPOSITORY.clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_valid_csv_upload_stores_holdings(client: TestClient) -> None:
    csv_content = (
        "ticker,exchange,asset_class,quantity,avg_buy_price,currency,purchase_date\n"
        "INFY,NSE,equity,3,1420.5,INR,2024-01-15\n"
    )

    response = client.post(
        "/api/v1/portfolio/imports",
        files={"file": ("portfolio.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["imported"] == 1
    assert payload["rejected"] == []
    assert payload["holdings"][0]["raw_ticker"] == "INFY"
    assert payload["holdings"][0]["canonical_ticker"] == "INFY.NS"

    holdings_response = client.get("/api/v1/portfolio/holdings")
    assert holdings_response.status_code == 200
    assert holdings_response.json()["holdings"][0]["raw_ticker"] == "INFY"


def test_second_csv_upload_replaces_existing_holdings(client: TestClient) -> None:
    first_csv = (
        "ticker,exchange,asset_class,quantity,avg_buy_price,currency,purchase_date\n"
        "INFY,NSE,equity,3,1420.5,INR,2024-01-15\n"
    )
    second_csv = (
        "ticker,exchange,asset_class,quantity,avg_buy_price,currency,purchase_date\n"
        "TCS,NSE,equity,2,3900,INR,2024-02-01\n"
    )

    first_response = client.post(
        "/api/v1/portfolio/imports",
        files={"file": ("portfolio.csv", first_csv, "text/csv")},
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/portfolio/imports",
        files={"file": ("portfolio.csv", second_csv, "text/csv")},
    )

    assert second_response.status_code == 201
    holdings = client.get("/api/v1/portfolio/holdings").json()["holdings"]
    assert len(holdings) == 1
    assert holdings[0]["raw_ticker"] == "TCS"


def test_portfolio_valuation_uses_market_quotes(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeMarketDataService:
        def get_quotes(self, tickers: list[str], exchanges: dict[str, str]):
            return {
                "INFY.NS": MarketDataEnvelope(
                    ticker="INFY.NS",
                    resolved_ticker="INFY.NS",
                    value={
                        "price": 1500,
                        "change": 12,
                        "change_percent": 0.8,
                        "currency": "INR",
                    },
                    is_stale=False,
                    source="test",
                )
            }

    monkeypatch.setattr(
        DEFAULT_PORTFOLIO_SERVICE,
        "market_data_service",
        FakeMarketDataService(),
    )
    csv_content = (
        "ticker,exchange,asset_class,quantity,avg_buy_price,currency,purchase_date\n"
        "INFY,NSE,equity,3,1420,INR,2024-01-15\n"
    )
    client.post(
        "/api/v1/portfolio/imports",
        files={"file": ("portfolio.csv", csv_content, "text/csv")},
    )

    response = client.get("/api/v1/portfolio/valuation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["invested_amount"] == 4260
    assert payload["current_value"] == 4500
    assert payload["unrealized_pnl"] == 240
    assert payload["today_pnl"] == 36
    assert payload["priced_holdings"] == 1
    assert payload["unpriced_holdings"] == 0
    assert payload["quotes"][0]["price"] == 1500


def test_csv_upload_rejects_missing_exchange_and_invalid_asset_class(
    client: TestClient,
) -> None:
    csv_content = (
        "ticker,exchange,asset_class,quantity,avg_buy_price,currency,purchase_date\n"
        "INFY,,equity,3,1420.5,INR,2024-01-15\n"
        "TCS,NSE,crypto,1,3900,INR,2024-02-01\n"
    )

    response = client.post(
        "/api/v1/portfolio/imports",
        files={"file": ("portfolio.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["imported"] == 0
    assert len(payload["rejected"]) == 2
    assert "Missing required columns: exchange" in payload["rejected"][0]["reason"]
    assert "Invalid asset_class" in payload["rejected"][1]["reason"]
    assert client.get("/api/v1/portfolio/holdings").json()["holdings"] == []


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("notes.txt", "risk notes for the portfolio"),
        ("thesis.md", "# Thesis\nHold unless drawdown changes."),
    ],
)
def test_artifact_upload_accepts_txt_and_md(
    client: TestClient,
    filename: str,
    content: str,
) -> None:
    response = client.post(
        "/api/v1/artifacts",
        files={"file": (filename, content, "text/plain")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["filename"] == filename
    assert payload["content"] == content
    assert payload["preview"]

    list_response = client.get("/api/v1/artifacts")
    assert list_response.status_code == 200
    assert list_response.json()["artifacts"][0]["filename"] == filename

    detail_response = client.get(f"/api/v1/artifacts/{payload['artifact_id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["content"] == content


@pytest.mark.parametrize("filename", ["report.pdf", "positions.csv", "README"])
def test_artifact_upload_rejects_unsupported_files(
    client: TestClient,
    filename: str,
) -> None:
    response = client.post(
        "/api/v1/artifacts",
        files={"file": (filename, "not accepted", "text/plain")},
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Only .txt and .md knowledge artifacts are supported."
    )
