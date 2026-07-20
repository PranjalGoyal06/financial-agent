from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session, init_db
from app.graph import get_agent
from app.market_data.router import router as market_data_router
from app.portfolio_service import (
    PortfolioValidationError,
    get_portfolio,
    replace_portfolio_from_csv,
)
from app.research.router import router as research_router
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
app.include_router(research_router)



# ── Helpers ────────────────────────────────────────────────────────────────────


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


async def _build_portfolio_context(session: AsyncSession) -> str:
    """Fetch the user's holdings and format them as a markdown table.

    Returns a concise markdown table if holdings exist, or a fallback string.
    The result is injected into the agent's system prompt so it can answer
    questions like 'what do I own?' or 'what's my largest position?' without
    calling a tool.
    """
    try:
        data = await get_portfolio(session, user_id=settings.default_user_id)
        holdings = data.get("holdings", [])
    except Exception:
        return "No portfolio data available."

    if not holdings:
        return "No portfolio data available (empty portfolio)."

    lines = [
        "| Ticker | Exchange | Asset | Qty | Avg Cost (₹) | Currency |",
        "|---|---|---|---|---|---|",
    ]
    for h in holdings:
        lines.append(
            f"| {h.get('canonical_ticker', '')} "
            f"| {h.get('exchange', '')} "
            f"| {h.get('asset_class', '')} "
            f"| {h.get('quantity', '')} "
            f"| {h.get('avg_cost', '')} "
            f"| {h.get('currency', '')} |"
        )
    if "realized_pnl" in data:
        lines.append(f"\nRealized P&L: ₹{data['realized_pnl']}")
    return "\n".join(lines)


def _tool_output_summary(tool_name: str, output: Any) -> str:
    """Produce a concise human-readable summary of a tool's output for the UI.

    The full tool output goes to the LLM; this summary is for the streaming
    indicator shown in the chat panel while the agent is reasoning.
    """
    text = str(output) if not isinstance(output, str) else output
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text[:120]

    if tool_name == "get_quote_tool":
        ticker = parsed.get("ticker", "")
        price = parsed.get("price")
        pct = parsed.get("day_change_pct")
        if price is not None:
            sign = "+" if (pct or 0) >= 0 else ""
            return f"{ticker}: ₹{price:,.2f} ({sign}{pct:.2f}%)"

    if tool_name == "resolve_asset_tool":
        candidates = parsed.get("candidates", [])
        if candidates:
            names = ", ".join(c.get("canonical_ticker", "") for c in candidates[:3])
            return f"Resolved → {names}"
        return "No matching ticker found"

    if tool_name == "get_historical_data_tool":
        ticker = parsed.get("ticker", "")
        pct = parsed.get("pct_change")
        period = parsed.get("period", "")
        if pct is not None:
            sign = "+" if pct >= 0 else ""
            return f"{ticker} ({period}): {sign}{pct:.2f}%"

    # Generic fallback: first 120 chars
    return text[:120]


# ── SSE streaming ──────────────────────────────────────────────────────────────


async def stream_chat_events(
    request: ChatRequest,
    session: AsyncSession,
) -> AsyncIterator[str]:
    yield sse(
        "run_start",
        {
            "stage": "chat_response",
            "user_id": settings.default_user_id,
            "timestamp": utc_now(),
        },
    )

    try:
        portfolio_context = await _build_portfolio_context(session)
        agent = get_agent(
            portfolio_context,
            provider=request.llm_provider,
            model=request.llm_model,
        )
    except ValueError as exc:
        yield sse("error", {"message": str(exc)})
        return

    try:
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=request.message)]},
            version="v2",
        ):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                token = event["data"]["chunk"].content
                if token:
                    yield sse("token", {"token": token})

            elif kind == "on_tool_start":
                tool_name = event.get("name", "tool")
                tool_input = event["data"].get("input", {})
                yield sse(
                    "tool_call",
                    {
                        "name": tool_name,
                        "status": "running",
                        "summary": f"Calling {tool_name.replace('_tool', '')}…",
                        "input": tool_input,
                    },
                )

            elif kind == "on_tool_end":
                tool_name = event.get("name", "tool")
                tool_output = event["data"].get("output", "")
                
                raw_content = getattr(tool_output, "content", str(tool_output))
                # ToolNode sets status="error" when ToolException is raised and
                # handle_tool_error=True. That's the authoritative signal — no
                # string heuristics needed.
                is_error = getattr(tool_output, "status", None) == "error"

                yield sse(
                    "tool_result",
                    {
                        "name": tool_name,
                        "status": "failed" if is_error else "done",
                        "summary": _tool_output_summary(tool_name, raw_content),
                        "output": raw_content,
                    },
                )

        resolved_provider = (request.llm_provider or settings.llm_provider).lower()
        if resolved_provider == "groq":
            active_model = request.llm_model or settings.groq_model or "unknown"
        else:
            active_model = request.llm_model or settings.ollama_model or "unknown"
        yield sse(
            "final",
            {
                "provider": resolved_provider,
                "model": active_model,
                "timestamp": utc_now(),
            },
        )

    except Exception as exc:
        yield sse("error", {"message": f"LLM Connection Failed: {exc!s}"})


# ── Endpoints ──────────────────────────────────────────────────────────────────


@app.get("/health", response_model=ChatHealthResponse)
def health() -> ChatHealthResponse:
    return ChatHealthResponse(
        status="ok",
        user_id=settings.default_user_id,
        runtime="chat",
    )


@app.post("/chat")
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    return StreamingResponse(
        stream_chat_events(request, session),
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
