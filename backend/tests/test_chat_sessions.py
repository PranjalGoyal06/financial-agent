from __future__ import annotations

from app.db.repositories.chat_repository import DEFAULT_CHAT_REPOSITORY
from app.main import app
from fastapi.testclient import TestClient


def setup_function() -> None:
    DEFAULT_CHAT_REPOSITORY.clear()


def test_session_lifecycle_supports_list_rename_and_delete() -> None:
    client = TestClient(app)

    created = client.post("/api/v1/chat/sessions", json={})

    assert created.status_code == 201
    session = created.json()
    session_id = session["session_id"]
    assert session["title"] == "New chat"
    assert session["message_count"] == 0

    listed = client.get("/api/v1/chat/sessions")
    assert listed.status_code == 200
    assert [item["session_id"] for item in listed.json()["sessions"]] == [session_id]

    fetched = client.get(f"/api/v1/chat/sessions/{session_id}")
    assert fetched.status_code == 200
    assert fetched.json()["session_id"] == session_id

    renamed = client.patch(
        f"/api/v1/chat/sessions/{session_id}",
        json={"title": "Downside review"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Downside review"

    deleted = client.delete(f"/api/v1/chat/sessions/{session_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/chat/sessions/{session_id}").status_code == 404
    assert client.get("/api/v1/chat/sessions").json()["sessions"] == []


def test_first_message_auto_titles_default_session_and_updates_counts() -> None:
    client = TestClient(app)
    session_id = client.post("/api/v1/chat/sessions", json={}).json()["session_id"]

    response = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Analyse concentration risk across my top holdings"},
    )

    assert response.status_code == 200
    session = client.get(f"/api/v1/chat/sessions/{session_id}").json()
    assert session["title"] == "Analyse concentration risk across my top holdings"
    assert session["message_count"] == 2
    assert session["last_message_at"] is not None

    history = client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    assert history.status_code == 200
    assert [message["role"] for message in history.json()["messages"]] == [
        "user",
        "assistant",
    ]
