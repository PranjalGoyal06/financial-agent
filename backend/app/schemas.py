from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatHealthResponse(BaseModel):
    status: str
    user_id: str
    runtime: str
