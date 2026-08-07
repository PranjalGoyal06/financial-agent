from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ChatSessionRecord:
    user_id: str
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    last_message_at: datetime | None = None
    message_count: int = 0
    deleted_at: datetime | None = None


@dataclass(slots=True)
class ChatMessageRecord:
    session_id: str
    role: str
    content: str
    graph_run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=_utc_now)


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        return _utc_now()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return _utc_now()


def _parse_optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return _parse_datetime(value)


def _session_payload(session: ChatSessionRecord) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "title": session.title,
        "metadata": session.metadata,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "last_message_at": session.last_message_at.isoformat()
        if session.last_message_at
        else None,
        "message_count": session.message_count,
        "deleted_at": session.deleted_at.isoformat() if session.deleted_at else None,
    }


def _message_payload(message: ChatMessageRecord) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "graph_run_id": message.graph_run_id,
        "metadata": message.metadata,
        "created_at": message.created_at.isoformat(),
    }


def _message_from_payload(payload: dict[str, Any]) -> ChatMessageRecord | None:
    session_id = payload.get("session_id")
    role = payload.get("role")
    content = payload.get("content")
    message_id = payload.get("message_id")
    if not all(
        isinstance(value, str) for value in [session_id, role, content, message_id]
    ):
        return None
    return ChatMessageRecord(
        session_id=session_id,
        role=role,
        content=content,
        graph_run_id=payload.get("graph_run_id"),
        metadata=payload.get("metadata") or {},
        message_id=message_id,
        created_at=_parse_datetime(payload.get("created_at")),
    )


class ChatRepository:
    def __init__(self, storage_path: Path | None = None) -> None:
        self._sessions: dict[str, ChatSessionRecord] = {}
        self._messages: dict[str, list[ChatMessageRecord]] = {}
        self._lock = RLock()
        self._storage_path = storage_path or Path("data/chat_sessions.json")
        self._load()

    def _load(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        sessions = payload.get("sessions", [])
        messages = payload.get("messages", {})
        if not isinstance(sessions, list) or not isinstance(messages, dict):
            return

        for raw_session in sessions:
            if not isinstance(raw_session, dict):
                continue
            session_id = raw_session.get("session_id")
            user_id = raw_session.get("user_id")
            if not isinstance(session_id, str) or not isinstance(user_id, str):
                continue
            session = ChatSessionRecord(
                session_id=session_id,
                user_id=user_id,
                title=raw_session.get("title"),
                metadata=raw_session.get("metadata") or {},
                created_at=_parse_datetime(raw_session.get("created_at")),
                updated_at=_parse_datetime(raw_session.get("updated_at")),
                last_message_at=_parse_optional_datetime(
                    raw_session.get("last_message_at")
                ),
                message_count=int(raw_session.get("message_count") or 0),
                deleted_at=_parse_optional_datetime(raw_session.get("deleted_at")),
            )
            self._sessions[session.session_id] = session

        for session_id, raw_messages in messages.items():
            if not isinstance(session_id, str) or not isinstance(raw_messages, list):
                continue
            self._messages[session_id] = [
                message
                for raw_message in raw_messages
                if isinstance(raw_message, dict)
                and (message := _message_from_payload(raw_message)) is not None
            ]

    def _save(self) -> None:
        payload = {
            "sessions": [
                _session_payload(session) for session in self._sessions.values()
            ],
            "messages": {
                session_id: [_message_payload(message) for message in messages]
                for session_id, messages in self._messages.items()
            },
        }
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(
            json.dumps(payload, separators=(",", ":"), default=str),
            encoding="utf-8",
        )

    def create_session(
        self, *, user_id: str, title: str | None, metadata: dict[str, Any]
    ) -> ChatSessionRecord:
        session = ChatSessionRecord(
            user_id=user_id,
            title=title,
            metadata=dict(metadata),
        )
        with self._lock:
            self._sessions[session.session_id] = session
            self._messages[session.session_id] = []
            self._save()
        return session

    def get_session(self, session_id: str) -> ChatSessionRecord | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.deleted_at is not None:
                return None
            return session

    def list_sessions(self, user_id: str) -> list[ChatSessionRecord]:
        with self._lock:
            sessions = [
                session
                for session in self._sessions.values()
                if session.user_id == user_id and session.deleted_at is None
            ]
        return sorted(
            sessions,
            key=lambda session: session.last_message_at
            or session.updated_at
            or session.created_at,
            reverse=True,
        )

    def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatSessionRecord | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.deleted_at is not None:
                return None
            if title is not None:
                session.title = title
            if metadata is not None:
                session.metadata = dict(metadata)
            session.updated_at = _utc_now()
            self._save()
            return session

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.deleted_at is not None:
                return False
            session.deleted_at = _utc_now()
            session.updated_at = session.deleted_at
            self._save()
            return True

    def append_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        graph_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessageRecord:
        message = ChatMessageRecord(
            session_id=session_id,
            role=role,
            content=content,
            graph_run_id=graph_run_id,
            metadata=metadata or {},
        )
        with self._lock:
            self._messages.setdefault(session_id, []).append(message)
            session = self._sessions.get(session_id)
            if session is not None:
                session.message_count += 1
                session.last_message_at = message.created_at
                session.updated_at = message.created_at
            self._save()
        return message

    def list_messages(self, session_id: str) -> list[ChatMessageRecord]:
        with self._lock:
            return list(self._messages.get(session_id, []))

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._messages.clear()
            if self._storage_path.exists():
                self._storage_path.unlink()


DEFAULT_CHAT_REPOSITORY = ChatRepository()
