from __future__ import annotations

import json

import pytest
from app.agents.reactive.nodes import parse_validate_output, validate_retrieval_plan
from app.agents.reactive.schemas import LLMOutput
from app.agents.reactive.state import ReactiveState
from app.db.repositories.audit_repository import DEFAULT_AUDIT_REPOSITORY
from app.db.repositories.chat_repository import DEFAULT_CHAT_REPOSITORY
from app.db.repositories.holdings_repository import (
    DEFAULT_HOLDINGS_REPOSITORY,
    HoldingRecord,
)
from app.db.repositories.recommendations_repository import (
    DEFAULT_RECOMMENDATIONS_REPOSITORY,
)
from app.main import app
from app.services.market_data_service import (
    DEFAULT_MARKET_DATA_SERVICE,
    MarketDataEnvelope,
)
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_reactive_repositories() -> None:
    DEFAULT_HOLDINGS_REPOSITORY.clear()
    DEFAULT_AUDIT_REPOSITORY.clear()
    DEFAULT_RECOMMENDATIONS_REPOSITORY.clear()
    DEFAULT_CHAT_REPOSITORY.clear()


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


def _final_event(response_text: str) -> dict[str, object]:
    events = _sse_events(response_text)
    final = [event for event in events if event["event"] == "final_response"]
    assert final
    return final[-1]


def test_general_question_returns_plain_chat_without_market_data(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_market_call(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("general questions must not fetch market data")

    monkeypatch.setattr(DEFAULT_MARKET_DATA_SERVICE, "get_quotes", fail_market_call)
    session_id = _session_id(client)

    response = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "What is beta?"},
    )

    assert response.status_code == 200
    payload = _final_event(response.text)
    message = payload["data"]["message"]  # type: ignore[index]
    response_metadata = message["metadata"]["response"]  # type: ignore[index]
    assert response_metadata["response_type"] == "plain_chat"
    assert response_metadata["card_payload"] is None
    assert message["content"] == response_metadata["bubble_text"]  # type: ignore[index]


def test_recommendation_with_unavailable_market_data_returns_insufficient_data(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    DEFAULT_HOLDINGS_REPOSITORY.insert_many(
        [
            HoldingRecord(
                user_id="demo-user",
                raw_ticker="INFY",
                canonical_ticker="INFY.NS",
                exchange="NSE",
                asset_class="equity",
                quantity=3,
                avg_buy_price=1420.5,
                currency="INR",
                purchase_date="2024-01-15",
            )
        ]
    )

    monkeypatch.setattr(
        DEFAULT_MARKET_DATA_SERVICE,
        "get_quotes",
        lambda tickers: {
            ticker: MarketDataEnvelope(
                ticker=ticker,
                resolved_ticker=ticker,
                value=None,
                is_stale=True,
                source="yfinance",
            )
            for ticker in tickers
        },
    )
    session_id = _session_id(client)

    response = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Should I add INFY.NS?"},
    )

    assert response.status_code == 200
    payload = _final_event(response.text)
    message = payload["data"]["message"]  # type: ignore[index]
    response_metadata = message["metadata"]["response"]  # type: ignore[index]
    assert response_metadata["response_type"] == "insufficient_data"
    assert response_metadata["data_quality"] == "critical_failure"
    assert "market snapshots" in response_metadata["bubble_text"]


def test_portfolio_risk_with_unavailable_market_data_returns_snapshot(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    DEFAULT_HOLDINGS_REPOSITORY.insert_many(
        [
            HoldingRecord(
                user_id="demo-user",
                raw_ticker="INFY",
                canonical_ticker="INFY.NS",
                exchange="NSE",
                asset_class="equity",
                quantity=3,
                avg_buy_price=1420.5,
                currency="INR",
                purchase_date="2024-01-15",
            )
        ]
    )

    monkeypatch.setattr(
        DEFAULT_MARKET_DATA_SERVICE,
        "get_quotes",
        lambda tickers: {
            ticker: MarketDataEnvelope(
                ticker=ticker,
                resolved_ticker=ticker,
                value=None,
                is_stale=True,
                source="yfinance",
            )
            for ticker in tickers
        },
    )
    session_id = _session_id(client)

    response = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Analyse my portfolio risk"},
    )

    assert response.status_code == 200
    payload = _final_event(response.text)
    message = payload["data"]["message"]  # type: ignore[index]
    response_metadata = message["metadata"]["response"]  # type: ignore[index]
    assert response_metadata["response_type"] == "portfolio_snapshot"
    assert response_metadata["data_quality"] == "limited"
    assert response_metadata["card_payload"]["total_holdings"] == 1


def test_message_history_preserves_response_envelope(client: TestClient) -> None:
    session_id = _session_id(client)
    response = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "hello"},
    )
    assert response.status_code == 200

    history = client.get(f"/api/v1/chat/sessions/{session_id}/messages")

    assert history.status_code == 200
    messages = history.json()["messages"]
    assistant = [message for message in messages if message["role"] == "assistant"][-1]
    assert assistant["metadata"]["response"]["response_type"] == "plain_chat"
    assert assistant["content"] == assistant["metadata"]["response"]["bubble_text"]


@pytest.mark.parametrize(
    ("query", "expected_intent", "tickers"),
    [
        ("What is beta?", "general_question", []),
        ("Should I buy INFY.NS?", "recommendation", ["INFY.NS"]),
        ("Analyse my portfolio risk", "risk_analysis", []),
        ("Compare TCS.NS and INFY.NS", "comparison", ["TCS.NS", "INFY.NS"]),
        ("Latest news on RELIANCE.NS", "news_impact", ["RELIANCE.NS"]),
    ],
)
def test_intent_validation_preserves_expected_intents(
    query: str,
    expected_intent: str,
    tickers: list[str],
) -> None:
    state: ReactiveState = {
        "session_id": "s1",
        "graph_run_id": "g1",
        "user_id": "demo-user",
        "user_query": query,
        "user_profile": {"user_id": "demo-user"},
        "portfolio": {"holdings": []},
        "watchlist": [],
        "principles": [],
        "investment_principles": [],
        "recent_chat_context": [],
        "data_freshness_status": {},
        "retrieval_plan": {
            "intent": expected_intent,
            "relevant_tickers": tickers,
            "reason_for_retrieval": "test",
        },
        "retrieval_disclosure": {},
        "relevant_tickers": [],
        "market_data": {},
        "retrieved_chunks": [],
        "evidence_pack": [],
        "prior_recommendations": [],
        "data_quality": {},
        "data_quality_verdict": "ok",
        "data_quality_passed": True,
        "data_quality_flags": [],
        "compressed_context": "",
        "principle_conflicts": [],
        "raw_analysis": "",
        "llm_raw_output": "",
        "parsed_output": {},
        "recommendation": {},
        "validation_errors": [],
        "final_response": {},
        "audit_events": [],
        "messages": [],
        "reasoning_trace": [],
    }

    update = validate_retrieval_plan(state)

    assert update["retrieval_plan"]["intent"] == expected_intent


def test_invalid_llm_evidence_ids_are_stripped() -> None:
    output = LLMOutput(
        response_type="plain_chat",
        bubble_text="Test",
        card_payload=None,
        evidence_ids_used=["valid_id", "invalid_id"],
        confidence_tier="medium",
    )
    state: ReactiveState = {
        "session_id": "s1",
        "graph_run_id": "g1",
        "user_id": "demo-user",
        "user_query": "test",
        "user_profile": {"user_id": "demo-user"},
        "portfolio": {"holdings": []},
        "watchlist": [],
        "principles": [],
        "investment_principles": [],
        "recent_chat_context": [],
        "data_freshness_status": {},
        "retrieval_plan": {
            "intent": "general_question",
            "relevant_tickers": [],
            "reason_for_retrieval": "test",
        },
        "retrieval_disclosure": {},
        "relevant_tickers": [],
        "market_data": {},
        "retrieved_chunks": [],
        "evidence_pack": [
            {
                "evidence_id": "valid_id",
                "source_type": "portfolio",
                "ticker": None,
                "provider": "test",
                "fetched_at": "2026-06-21T00:00:00+00:00",
                "quality_tier": "fresh",
                "payload": {},
                "failure_reason": None,
            }
        ],
        "prior_recommendations": [],
        "data_quality": {"overall": "good"},
        "data_quality_verdict": "ok",
        "data_quality_passed": True,
        "data_quality_flags": [],
        "compressed_context": "",
        "principle_conflicts": [],
        "raw_analysis": "",
        "llm_raw_output": output.model_dump_json(),
        "parsed_output": {},
        "recommendation": {},
        "validation_errors": [],
        "final_response": {},
        "audit_events": [],
        "messages": [],
        "reasoning_trace": [],
    }

    update = parse_validate_output(state)

    assert update["parsed_output"]["evidence_ids_used"] == ["valid_id"]
    assert update["validation_errors"]
