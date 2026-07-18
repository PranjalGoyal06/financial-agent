from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

# ── Constants ──────────────────────────────────────────────────────────────────

_NO_PORTFOLIO = "No portfolio data available."
_PORTFOLIO_PATCH = patch(
    "app.main._build_portfolio_context",
    new_callable=AsyncMock,
    return_value=_NO_PORTFOLIO,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_agent_stub(events: list[dict]) -> MagicMock:
    """Build a fake agent whose astream_events yields the given event dicts."""

    async def _astream(inputs, version="v2"):
        for evt in events:
            yield evt

        # Make it an async generator
        if False:
            yield

    stub = MagicMock()
    stub.astream_events = _astream
    return stub


def _token_events(text: str) -> list[dict]:
    """Produce on_chat_model_stream events for each character in text."""
    return [
        {
            "event": "on_chat_model_stream",
            "name": "ChatGroq",
            "data": {"chunk": MagicMock(content=ch)},
        }
        for ch in text
    ]


def _tool_start_event(name: str, inputs: dict) -> dict:
    return {"event": "on_tool_start", "name": name, "data": {"input": inputs}}


def _tool_end_event(name: str, output: str) -> dict:
    return {"event": "on_tool_end", "name": name, "data": {"output": output}}


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_health_reports_chat_runtime(client: TestClient) -> None:
    """Verify that the health check endpoint returns 200 and the correct runtime."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["runtime"] == "chat"
    assert "user_id" in body


def test_chat_streams_token_and_final_events(client: TestClient) -> None:
    """Verify that /chat streams run_start, token, and final events correctly."""
    stub = _make_agent_stub(_token_events("Hello world"))

    with (
        patch("app.main.get_agent", return_value=stub),
        _PORTFOLIO_PATCH,
    ):
        response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: run_start" in body
    assert "event: token" in body
    assert "event: final" in body
    # Tokens stream character-by-character; verify a few appear individually
    assert '"token":"H"' in body
    assert '"token":"e"' in body


def test_chat_streams_tool_call_events(client: TestClient) -> None:
    """tool_call and tool_result SSE events must appear when agent uses a tool."""
    quote_json = json.dumps(
        {"ticker": "INFY.NS", "price": 1523.0, "day_change_pct": 0.84}
    )
    stub = _make_agent_stub(
        [
            _tool_start_event("get_quote_tool", {"ticker": "INFY.NS"}),
            _tool_end_event("get_quote_tool", quote_json),
            *_token_events("The price is ₹1,523."),
        ]
    )

    with (
        patch("app.main.get_agent", return_value=stub),
        _PORTFOLIO_PATCH,
    ):
        response = client.post("/chat", json={"message": "INFY price?"})

    body = response.text
    assert "event: tool_call" in body
    assert "event: tool_result" in body
    assert "get_quote_tool" in body


def test_chat_streams_error_when_llm_unconfigured(client: TestClient) -> None:
    """Verify that ValueError from LLM configuration is streamed as an SSE error."""
    with (
        patch(
            "app.main.get_agent",
            side_effect=ValueError("Groq API key or model is not configured."),
        ),
        _PORTFOLIO_PATCH,
    ):
        response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 200
    body = response.text
    assert "event: error" in body
    assert "Groq API key" in body


def test_chat_streams_error_on_graph_failure(client: TestClient) -> None:
    """Verify that unhandled graph exceptions are caught and streamed as SSE errors."""
    async def _bad_astream(inputs, version="v2"):
        raise RuntimeError("Graph exploded")
        yield  # make it an async generator

    stub = MagicMock()
    stub.astream_events = _bad_astream

    with (
        patch("app.main.get_agent", return_value=stub),
        _PORTFOLIO_PATCH,
    ):
        response = client.post("/chat", json={"message": "Hello"})

    body = response.text
    assert "event: error" in body
    assert "Graph exploded" in body


def test_chat_rejects_empty_message(client: TestClient) -> None:
    """Verify that an empty chat message is rejected with 422 Unprocessable Entity."""
    response = client.post("/chat", json={"message": ""})
    assert response.status_code == 422
