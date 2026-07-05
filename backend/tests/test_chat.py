from __future__ import annotations

import pytest
from app.config import settings
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


def test_chat_streams_token_and_final_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "groq_model", None)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: run_start" in body
    assert "event: token" in body
    assert "event: final" in body
    assert "SCALE Finance Agent is connected" in body


def test_chat_rejects_empty_message() -> None:
    client = TestClient(app)

    response = client.post("/chat", json={"message": ""})

    assert response.status_code == 422
