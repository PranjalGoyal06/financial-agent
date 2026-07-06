from __future__ import annotations

from unittest.mock import patch

from app.main import app
from fastapi.testclient import TestClient


def test_health_reports_chat_runtime() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "user_id": "local-user",
        "runtime": "chat",
    }


def test_chat_streams_token_and_final_events() -> None:
    client = TestClient(app)
    mock_result = {
        "response": "Hello world response",
        "tokens": ["Hello", " ", "world", " ", "response"],
        "model": "llama-3.1-8b-instant",
        "used_local_response": False,
    }

    with patch("app.main.chat_graph.invoke", return_value=mock_result):
        response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: run_start" in body
    assert "event: token" in body
    assert "event: final" in body
    assert "Hello world response" in body


def test_chat_streams_error_on_failure() -> None:
    client = TestClient(app)

    with patch(
        "app.main.chat_graph.invoke",
        side_effect=ValueError("Graph Execution Failed"),
    ):
        response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 200
    body = response.text
    assert "event: run_start" in body
    assert "event: error" in body
    assert "Graph Execution Failed" in body


def test_chat_rejects_empty_message() -> None:
    client = TestClient(app)

    response = client.post("/chat", json={"message": ""})

    assert response.status_code == 422
