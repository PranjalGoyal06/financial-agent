from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import asyncio

from app.config import settings
from app.db import get_session, init_db
from app.graph import get_agent
from app.market_data.router import router as market_data_router
from app.portfolio_service import (
    PortfolioValidationError,
    get_portfolio,
    replace_portfolio_from_csv,
)
from app.portfolio.lib import get_ticker_recommendation
from app.market_data.provider import YFinanceProvider
from app.market_data.schemas import MarketQuote
from app.research.router import router as research_router
from app.briefing.router import router as briefing_router
from app.search.stocks_router import router as stocks_router
from app.schemas import ChatHealthResponse, ChatRequest, ServiceStatus


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
app.include_router(briefing_router)
app.include_router(stocks_router, prefix="/api/search")



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

_health_cache: dict[str, Any] = {"status": "healthy", "checks": {}, "timestamp": 0.0}
HEALTH_CACHE_TTL = 10.0


@app.get("/health", response_model=ChatHealthResponse)
async def health(session: AsyncSession = Depends(get_session)) -> ChatHealthResponse:
    now = time.time()
    if now - _health_cache["timestamp"] < HEALTH_CACHE_TTL and _health_cache["checks"]:
        return ChatHealthResponse(
            status=_health_cache["status"],
            user_id=settings.default_user_id,
            runtime="chat",
            checks=_health_cache["checks"]
        )

    checks = {}

    # 1. Database
    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=2.0)
        checks["database"] = ServiceStatus(ok=True, latency_ms=round((time.perf_counter()-t0)*1000, 2))
    except Exception as e:
        checks["database"] = ServiceStatus(ok=False, latency_ms=round((time.perf_counter()-t0)*1000, 2), message=str(e))

    # 2. ChromaDB
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            res = await client.get(f"http://{settings.chroma_host}:{settings.chroma_port}/api/v1/heartbeat")
            res.raise_for_status()
            checks["chroma"] = ServiceStatus(ok=True, latency_ms=round((time.perf_counter()-t0)*1000, 2))
    except Exception as e:
        checks["chroma"] = ServiceStatus(ok=False, latency_ms=round((time.perf_counter()-t0)*1000, 2), message=str(e))

    # 3. LLM Provider
    t0 = time.perf_counter()
    provider = settings.llm_provider.lower()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            if provider == "groq":
                if not settings.groq_api_key:
                    raise ValueError("Groq API key not set")
                res = await client.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {settings.groq_api_key}"})
                res.raise_for_status()
            elif provider == "ollama":
                res = await client.get(f"{settings.ollama_base_url}/api/tags")
                res.raise_for_status()
            else:
                raise ValueError("Unknown provider")
            checks["llm_provider"] = ServiceStatus(ok=True, latency_ms=round((time.perf_counter()-t0)*1000, 2), provider=provider)
    except Exception as e:
        checks["llm_provider"] = ServiceStatus(ok=False, latency_ms=round((time.perf_counter()-t0)*1000, 2), provider=provider, message=str(e))

    # Evaluate tri-state
    is_db_ok = checks["database"].ok
    is_llm_ok = checks["llm_provider"].ok
    is_chroma_ok = checks["chroma"].ok

    if not is_db_ok or not is_llm_ok:
        status_code = "unhealthy"
    elif not is_chroma_ok:
        status_code = "degraded"
    else:
        status_code = "healthy"

    _health_cache["status"] = status_code
    _health_cache["checks"] = checks
    _health_cache["timestamp"] = now

    return ChatHealthResponse(
        status=status_code,
        user_id=settings.default_user_id,
        runtime="chat",
        checks=checks
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


_quote_provider = YFinanceProvider()


def _to_yf_symbol(ticker: str, exchange: str | None = None) -> str:
    upper = ticker.upper()
    if upper.endswith(".NS") or upper.endswith(".BO"):
        return upper
    if exchange and exchange.upper() in ("BSE", "BO"):
        return f"{upper}.BO"
    return f"{upper}.NS"


def _get_sparkline(yf_symbol: str) -> list[float]:
    try:
        t = yf.Ticker(yf_symbol)
        df = t.history(period="5d")
        if df is not None and not df.empty:
            closes = df["Close"].dropna().tolist()
            return [round(float(c), 2) for c in closes]
    except Exception as e:
        import traceback
        print(f"Sparkline error for {yf_symbol}: {e}\n{traceback.format_exc()}")
    return []


def _fetch_sparkline_real(yf_symbol: str) -> list[float]:
    try:
        hist = _quote_provider.get_historical(yf_symbol, period="1mo", interval="1d")
        if hist and hist.bars:
            return [round(float(b.close), 2) for b in hist.bars]
    except Exception as e:
        print(f"Sparkline fetch error for {yf_symbol}: {e}")
    return []


async def _fetch_quote_safe(ticker: str, exchange: str | None = None) -> dict[str, Any]:
    yf_symbol = _to_yf_symbol(ticker, exchange)
    try:
        quote = await asyncio.to_thread(_quote_provider.get_quote, yf_symbol)
        quote_dict = quote.model_dump(mode="json")
        sparkline = await asyncio.to_thread(_fetch_sparkline_real, yf_symbol)
        quote_dict["sparkline"] = sparkline
        return quote_dict
    except Exception as e:
        if not (ticker.upper().endswith(".NS") or ticker.upper().endswith(".BO")):
            alt_symbol = (
                f"{ticker.upper()}.BO"
                if yf_symbol.endswith(".NS")
                else f"{ticker.upper()}.NS"
            )
            try:
                quote = await asyncio.to_thread(_quote_provider.get_quote, alt_symbol)
                quote_dict = quote.model_dump(mode="json")
                sparkline = await asyncio.to_thread(_fetch_sparkline_real, alt_symbol)
                quote_dict["sparkline"] = sparkline
                return quote_dict
            except Exception:
                pass
        return {"error": str(e)}


@app.get("/portfolio/quotes")
async def portfolio_quotes(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    portfolio_data = await get_portfolio(session, user_id=settings.default_user_id)
    holdings = portfolio_data.get("holdings", [])

    # Map canonical_ticker -> exchange
    ticker_exchanges: dict[str, str | None] = {}
    for h in holdings:
        canonical = h.get("canonical_ticker")
        if canonical and h.get("asset_class") in ("equity", "etf"):
            ticker_exchanges[canonical] = h.get("exchange")

    if not ticker_exchanges:
        return {}

    tickers = list(ticker_exchanges.keys())
    results = await asyncio.gather(
        *(_fetch_quote_safe(t, ticker_exchanges[t]) for t in tickers)
    )
    return {ticker: res for ticker, res in zip(tickers, results)}


@app.get("/portfolio/valued")
async def portfolio_valued(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    portfolio_data = await get_portfolio(session, user_id=settings.default_user_id)
    holdings = portfolio_data.get("holdings", [])
    
    if not holdings:
        return {
            "summary": {
                "total_market_value": 0.0,
                "total_unrealized_pnl": 0.0,
                "realized_pnl": float(portfolio_data.get("realized_pnl", 0))
            },
            "holdings": []
        }

    ticker_exchanges: dict[str, str | None] = {}
    for h in holdings:
        canonical = h.get("canonical_ticker")
        if canonical and h.get("asset_class") in ("equity", "etf"):
            ticker_exchanges[canonical] = h.get("exchange")

    tickers = list(ticker_exchanges.keys())
    
    quote_coros = [_fetch_quote_safe(t, ticker_exchanges[t]) for t in tickers]
    quote_results = await asyncio.gather(*quote_coros)
    recommendation_results = [await get_ticker_recommendation(session, t) for t in tickers]
    
    quotes_by_ticker = {ticker: res for ticker, res in zip(tickers, quote_results)}
    recommendations_by_ticker = {ticker: res for ticker, res in zip(tickers, recommendation_results)}

    total_market_value = 0.0
    total_invested = 0.0

    valued_holdings = []
    for h in holdings:
        canonical = h.get("canonical_ticker")
        quote = quotes_by_ticker.get(canonical, {})
        rec = recommendations_by_ticker.get(canonical) or {}
        
        qty = float(h.get("quantity", 0))
        avg_cost = float(h.get("avg_cost", 0))
        invested = qty * avg_cost
        
        price = quote.get("price")
        market_value = None
        unrealized_pnl_pct = None
        
        if price is not None:
            market_value = qty * float(price)
            if invested > 0:
                unrealized_pnl_pct = ((market_value - invested) / invested) * 100
            total_market_value += market_value
            total_invested += invested
            
        row = dict(h)
        row["market_value"] = market_value
        row["unrealized_pnl_pct"] = unrealized_pnl_pct
        row["recommendation"] = rec.get("recommendation")
        row["confidence_score"] = rec.get("confidence_score")
        row["last_updated"] = rec.get("last_updated").isoformat() if rec.get("last_updated") else None
        row["run_id"] = rec.get("run_id")
        
        valued_holdings.append(row)

    total_unrealized_pnl = 0.0
    if total_invested > 0:
        total_unrealized_pnl = total_market_value - total_invested
        
    return {
        "summary": {
            "total_market_value": total_market_value,
            "total_unrealized_pnl": total_unrealized_pnl,
            "realized_pnl": float(portfolio_data.get("realized_pnl", 0))
        },
        "holdings": valued_holdings
    }


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
