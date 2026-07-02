from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.graph import chat_graph
from app.schemas import ChatHealthResponse, ChatRequest

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def stream_chat_events(request: ChatRequest) -> Iterator[str]:
    initial_state = {
        "user_id": settings.default_user_id,
        "message": request.message,
    }
    yield sse(
        "run_start",
        {
            "stage": "chat_response",
            "user_id": settings.default_user_id,
            "timestamp": utc_now(),
        },
    )

    result = chat_graph.invoke(initial_state)
    for token in result.get("tokens", []):
        yield sse("token", {"token": token})

    yield sse(
        "final",
        {
            "message": result.get("response", ""),
            "model": result.get("model", "unknown"),
            "used_local_response": bool(result.get("used_local_response", False)),
            "timestamp": utc_now(),
        },
    )


@app.get("/health", response_model=ChatHealthResponse)
def health() -> ChatHealthResponse:
    return ChatHealthResponse(
        status="ok",
        user_id=settings.default_user_id,
        runtime="chat",
    )


@app.post("/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_chat_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
