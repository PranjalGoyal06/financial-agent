from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

MessageRole = Literal["user", "assistant", "system"]


class ChatSessionCreateRequest(BaseModel):
    user_id: str = Field(default="demo-user", min_length=1)
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatSessionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] | None = None


class ChatSessionCreateResponse(BaseModel):
    session_id: str
    user_id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
    message_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionCreateResponse]


class ChatMessageCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessageResponse(BaseModel):
    message_id: str
    session_id: str
    role: MessageRole
    content: str
    created_at: datetime
    graph_run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessageHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessageResponse]


class ChatNodeCompleteEvent(BaseModel):
    event: Literal["node_complete"] = "node_complete"
    data: dict[str, Any]


class ChatFinalResponseEvent(BaseModel):
    event: Literal["final_response"] = "final_response"
    data: dict[str, Any]
