from __future__ import annotations

import asyncio
from collections.abc import Generator
from uuid import uuid4

import pytest
from app.config import settings
from app.db import AsyncSessionLocal, init_db
from app.main import app
from app.models import UserModel
from fastapi.testclient import TestClient
from sqlalchemy import delete


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    user_id = f"test-user-{uuid4()}"
    monkeypatch.setattr(settings, "default_user_id", user_id)
    asyncio.run(init_db())
    with TestClient(app) as test_client:
        yield test_client
    asyncio.run(_delete_test_user(user_id))


async def _delete_test_user(user_id: str) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(delete(UserModel).where(UserModel.id == user_id))


def test_valid_csv_upload_stores_holdings(client: TestClient) -> None:
    csv_content = (
        "ticker,exchange,asset_class,quantity,avg_buy_price,currency,purchase_date\n"
        "INFY.NS,NSE,equity,3,1420.5,INR,2024-01-15\n"
    )

    response = client.post(
        "/portfolio/upload",
        files={"file": ("portfolio.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["imported_count"] == 1
    assert payload["holdings"][0]["canonical_ticker"] == "INFY.NS"
    assert payload["holdings"][0]["avg_cost"] == 1420.5

    portfolio_response = client.get("/portfolio")
    assert portfolio_response.status_code == 200
    portfolio = portfolio_response.json()
    assert portfolio["total_holdings"] == 1
    assert portfolio["holdings"][0]["canonical_ticker"] == "INFY.NS"


def test_second_upload_replaces_existing_holdings(client: TestClient) -> None:
    first_csv = "ticker,quantity,avg_cost\nINFY.NS,3,1420.5\n"
    second_csv = "ticker,quantity,avg_cost\nTCS.NS,2,3900\n"

    first_response = client.post(
        "/portfolio/upload",
        files={"file": ("portfolio.csv", first_csv, "text/csv")},
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/portfolio/upload",
        files={"file": ("portfolio.csv", second_csv, "text/csv")},
    )
    assert second_response.status_code == 201

    holdings = client.get("/portfolio").json()["holdings"]
    assert len(holdings) == 1
    assert holdings[0]["canonical_ticker"] == "TCS.NS"


def test_invalid_upload_leaves_existing_holdings_untouched(client: TestClient) -> None:
    valid_csv = "ticker,quantity,avg_cost\nINFY.NS,3,1420.5\n"
    invalid_csv = "ticker,quantity,avg_cost\nTCS.NS,-2,3900\n"
    assert (
        client.post(
            "/portfolio/upload",
            files={"file": ("portfolio.csv", valid_csv, "text/csv")},
        ).status_code
        == 201
    )

    response = client.post(
        "/portfolio/upload",
        files={"file": ("portfolio.csv", invalid_csv, "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["errors"] == [
        {
            "row": 2,
            "field": "quantity",
            "message": "quantity must be positive.",
        }
    ]
    holdings = client.get("/portfolio").json()["holdings"]
    assert len(holdings) == 1
    assert holdings[0]["canonical_ticker"] == "INFY.NS"


def test_upload_rejects_non_csv_filename(client: TestClient) -> None:
    response = client.post(
        "/portfolio/upload",
        files={
            "file": (
                "notes.txt",
                "ticker,quantity,avg_cost\nAAPL,1,10\n",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Portfolio upload must be a CSV file."


def test_upload_rejects_malformed_utf8(client: TestClient) -> None:
    response = client.post(
        "/portfolio/upload",
        files={"file": ("portfolio.csv", b"\xff\xfe", "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Portfolio CSV must be UTF-8 encoded."
