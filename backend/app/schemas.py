from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
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
