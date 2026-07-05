from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session, init_db
from app.graph import chat_graph
from app.market_data.router import router as market_data_router
from app.portfolio_service import (
    PortfolioValidationError,
    get_portfolio,
    replace_portfolio_from_csv,
)
from app.schemas import ChatHealthResponse, ChatRequest


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(market_data_router)


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


@app.get("/portfolio")
async def portfolio(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    return await get_portfolio(session, user_id=settings.default_user_id)


@app.post("/portfolio/upload", status_code=status.HTTP_201_CREATED)
async def upload_portfolio(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> Any:
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": "Portfolio upload must be a CSV file.",
                "errors": [
                    {
                        "row": 1,
                        "field": "file",
                        "message": "filename must end with .csv.",
                    }
                ],
            },
        )

    try:
        csv_text = (await file.read()).decode("utf-8")
    except UnicodeDecodeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": "Portfolio CSV must be UTF-8 encoded.",
                "errors": [
                    {
                        "row": 1,
                        "field": "file",
                        "message": "file could not be decoded as UTF-8.",
                    }
                ],
            },
        )

    try:
        return await replace_portfolio_from_csv(
            session,
            user_id=settings.default_user_id,
            csv_text=csv_text,
            source_filename=filename,
        )
    except PortfolioValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=exc.as_response(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Portfolio persistence failed.",
        ) from exc
