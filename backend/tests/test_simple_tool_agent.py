from __future__ import annotations

import json

import pytest
from app.agents.simple_tool_agent import run_quant_analysis, run_simple_tool_agent
from app.api.v1 import chat as chat_api
from app.config import settings
from app.db.repositories.chat_repository import DEFAULT_CHAT_REPOSITORY
from app.db.repositories.holdings_repository import DEFAULT_HOLDINGS_REPOSITORY
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_repositories() -> None:
    DEFAULT_HOLDINGS_REPOSITORY.clear()
    DEFAULT_CHAT_REPOSITORY.clear()
    settings.chat_orchestration = "reactive_graph"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _session_id(client: TestClient) -> str:
    response = client.post("/api/v1/chat/sessions", json={})
    assert response.status_code == 201
    return response.json()["session_id"]


def _sse_events(response_text: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for block in response_text.strip().split("\n\n"):
        data_lines = [
            line.removeprefix("data: ")
            for line in block.splitlines()
            if line.startswith("data: ")
        ]
        if data_lines:
            events.append(json.loads("".join(data_lines)))
    return events


def test_simple_orchestration_streams_tool_calls_and_persists_trace(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.chat_orchestration = "simple_llm_tools"

    def fake_simple_agent(**_kwargs):  # type: ignore[no-untyped-def]
        yield {
            "event": "node_complete",
            "data": {"node_name": "llm_select_tools"},
        }
        yield {
            "event": "tool_call",
            "data": {
                "tool_call_id": "call-1",
                "name": "read_portfolio",
                "args": {},
                "status": "started",
                "summary": "Running read_portfolio",
            },
        }
        completed = {
            "tool_call_id": "call-1",
            "name": "read_portfolio",
            "args": {},
            "status": "completed",
            "summary": "Loaded 1 holdings",
        }
        yield {"event": "tool_call", "data": completed}
        yield {
            "event": "final",
            "data": {
                "content": "Portfolio loaded with one holding.",
                "response": {
                    "response_type": "portfolio_snapshot",
                    "bubble_text": "Portfolio loaded with one holding.",
                    "card_payload": {"summary": "Portfolio loaded with one holding."},
                    "confidence_tier": "medium",
                    "data_quality": "good",
                    "retrieval_disclosure": {
                        "deterministic": ["portfolio holdings"],
                        "llm_planned": ["read_portfolio({})"],
                        "unavailable": [],
                    },
                    "evidence_ids": [],
                    "assumptions": [],
                    "principle_conflicts": [],
                    "advisory_only": True,
                    "graph_run_id": "g1",
                },
                "tool_calls": [completed],
                "validation_errors": [],
            },
        }

    monkeypatch.setattr(chat_api, "run_simple_tool_agent", fake_simple_agent)
    session_id = _session_id(client)

    response = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "How is my portfolio doing?"},
    )

    assert response.status_code == 200
    events = _sse_events(response.text)
    assert [event["event"] for event in events].count("tool_call") == 2
    final = [event for event in events if event["event"] == "final_response"][-1]
    message = final["data"]["message"]  # type: ignore[index]
    assert message["metadata"]["tool_calls"][0]["name"] == "read_portfolio"  # type: ignore[index]
    assert (
        message["metadata"]["response"]["retrieval_disclosure"]["llm_planned"]  # type: ignore[index]
        == ["read_portfolio({})"]
    )


def test_simple_agent_missing_groq_config_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.agents.simple_tool_agent.settings.groq_api_key", None)
    monkeypatch.setattr("app.agents.simple_tool_agent.settings.groq_model", None)

    events = list(
        run_simple_tool_agent(
            user_id="demo-user",
            user_query="How is my portfolio doing?",
            graph_run_id="g1",
        )
    )

    final = events[-1]
    assert final["event"] == "final"
    response = final["data"]["response"]  # type: ignore[index]
    assert response["response_type"] == "error"
    assert response["data_quality"] == "critical_failure"
    assert "GROQ_API_KEY" in response["bubble_text"]


def test_run_quant_analysis_computes_concentration() -> None:
    portfolio = {
        "holdings": [
            {
                "raw_ticker": "INFY",
                "canonical_ticker": "INFY.NS",
                "asset_class": "equity",
                "quantity": 10,
                "avg_buy_price": 100,
            },
            {
                "raw_ticker": "TCS",
                "canonical_ticker": "TCS.NS",
                "asset_class": "equity",
                "quantity": 5,
                "avg_buy_price": 100,
            },
        ]
    }
    valuation = {
        "current_value": 2000,
        "unrealized_pnl": 500,
        "today_pnl": 20,
        "priced_holdings": 2,
        "unpriced_holdings": 0,
        "quotes": [
            {"canonical_ticker": "INFY.NS", "position_value": 1500},
            {"canonical_ticker": "TCS.NS", "position_value": 500},
        ],
    }

    result = run_quant_analysis(portfolio=portfolio, valuation=valuation)

    assert result["total_holdings"] == 2
    assert result["invested_amount"] == 1500
    assert result["largest_position_weight"] == 75
    assert result["concentration_flag"] is True
    assert result["top_exposure"][0]["ticker"] == "INFY.NS"


def test_run_quant_analysis_ignores_empty_llm_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.agents.simple_tool_agent._read_portfolio",
        lambda _user_id: {
            "holdings": [
                {
                    "raw_ticker": "INFY",
                    "canonical_ticker": "INFY.NS",
                    "asset_class": "equity",
                    "quantity": 10,
                    "avg_buy_price": 100,
                }
            ]
        },
    )
    monkeypatch.setattr(
        "app.agents.simple_tool_agent._get_portfolio_valuation",
        lambda: {
            "current_value": None,
            "unrealized_pnl": None,
            "today_pnl": None,
            "priced_holdings": 0,
            "unpriced_holdings": 1,
            "quotes": [],
        },
    )

    result = run_quant_analysis(portfolio={"holdings": []}, valuation={})

    assert result["total_holdings"] == 1
    assert result["invested_amount"] == 1000
    assert result["top_exposure"][0]["ticker"] == "INFY.NS"
