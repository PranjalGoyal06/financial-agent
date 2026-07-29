from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = Field(default=None, description="Chat thread ID for checkpointer context memory.")
    mentions: list[dict[str, Any]] = Field(default_factory=list, description="List of recognized mentions.")
    llm_provider: str | None = Field(
        default=None,
        description="LLM provider override: 'groq' or 'ollama'. Defaults to the server setting.",
    )
    llm_model: str | None = Field(
        default=None,
        description="Model name override. Defaults to the server setting for the resolved provider.",
    )


class ServiceStatus(BaseModel):
    ok: bool
    latency_ms: float | None = None
    provider: str | None = None
    last_success: str | None = None
    message: str | None = None


class ChatHealthResponse(BaseModel):
    status: str
    user_id: str
    runtime: str
    checks: dict[str, ServiceStatus] = Field(default_factory=dict)


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    thinking: str | None = None
    blocks_json: list[dict[str, Any]] | None = None
    tool_calls: dict[str, Any] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    created_at: str


class ChatSessionUpdateRequest(BaseModel):
    title: str

class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessageResponse] = Field(default_factory=list)


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionResponse]
