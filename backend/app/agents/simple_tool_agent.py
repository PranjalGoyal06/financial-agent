from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any

from app.agents.reactive.schemas import FinalResponse
from app.config import settings
from app.db.repositories.holdings_repository import DEFAULT_HOLDINGS_REPOSITORY
from app.integrations import yfinance_client
from app.services.market_data_service import DEFAULT_MARKET_DATA_SERVICE
from app.services.portfolio_service import DEFAULT_PORTFOLIO_SERVICE

MAX_TOOL_CALLS = 6
SIMPLE_TOOL_NODES = {
    "select_tools": "llm_select_tools",
    "final_answer": "llm_final_answer",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=_json_default))


def _tool_summary(name: str, result: dict[str, Any]) -> str:
    if name == "read_portfolio":
        return f"Loaded {len(result.get('holdings', []))} holdings"
    if name == "get_portfolio_valuation":
        return (
            f"Valued {result.get('priced_holdings', 0)} priced holdings"
            f" with {result.get('unpriced_holdings', 0)} unpriced"
        )
    if name == "get_market_data":
        quotes = result.get("quotes", {})
        quote_count = len(quotes) if isinstance(quotes, dict) else 0
        return f"Fetched quotes for {quote_count} tickers"
    if name == "get_news":
        return f"Retrieved {len(result.get('articles', []))} articles"
    if name == "run_quant_analysis":
        return "Calculated allocation, concentration, and portfolio totals"
    return "Tool completed"


def _error_response(message: str, graph_run_id: str) -> dict[str, Any]:
    return FinalResponse(
        response_type="error",
        bubble_text=message,
        card_payload={"message": message, "recoverable": True},
        confidence_tier="insufficient",
        data_quality="critical_failure",
        retrieval_disclosure={
            "deterministic": [],
            "llm_planned": [],
            "unavailable": [{"item": "simple_llm_tools", "reason": message}],
        },
        evidence_ids=[],
        assumptions=[],
        principle_conflicts=[],
        graph_run_id=graph_run_id,
    ).model_dump(mode="json")


def _read_portfolio(user_id: str) -> dict[str, Any]:
    holdings = DEFAULT_HOLDINGS_REPOSITORY.list_by_user(user_id)
    return {"holdings": [asdict(holding) for holding in holdings]}


def _get_portfolio_valuation() -> dict[str, Any]:
    return _jsonable(DEFAULT_PORTFOLIO_SERVICE.portfolio_valuation())


def _get_market_data(tickers: list[str]) -> dict[str, Any]:
    envelopes = DEFAULT_MARKET_DATA_SERVICE.get_quotes(tickers)
    quotes: dict[str, Any] = {}
    for ticker, envelope in envelopes.items():
        quotes[ticker] = {
            "ticker": envelope.ticker,
            "resolved_ticker": envelope.resolved_ticker,
            "value": envelope.value,
            "is_stale": envelope.is_stale,
            "source": envelope.source,
            "error": asdict(envelope.error) if envelope.error else None,
        }
    return {"quotes": _jsonable(quotes)}


def _get_news(ticker: str) -> dict[str, Any]:
    result = yfinance_client.get_news(ticker)
    if isinstance(result, dict):
        result = result.get(ticker) or result.get(ticker.upper()) or next(
            iter(result.values())
        )
    if not result.ok or result.value is None:
        return {
            "ticker": ticker,
            "resolved_ticker": result.resolved_ticker,
            "articles": [],
            "error": asdict(result.error) if result.error else {"code": "fetch_failed"},
            "fetched_at": result.fetched_at,
        }
    return {
        "ticker": ticker,
        "resolved_ticker": result.resolved_ticker,
        "articles": result.value.get("articles", []),
        "error": None,
        "fetched_at": result.fetched_at,
    }


def run_quant_analysis(
    portfolio: dict[str, Any] | None = None,
    valuation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate portfolio allocation, concentration, P&L, and exposure metrics."""
    portfolio = portfolio or _read_portfolio("demo-user")
    if not portfolio.get("holdings"):
        portfolio = _read_portfolio("demo-user")
    valuation = valuation or _get_portfolio_valuation()
    if not valuation.get("quotes") and valuation.get("invested_amount") in {None, 0}:
        valuation = _get_portfolio_valuation()
    holdings = [
        holding
        for holding in portfolio.get("holdings", [])
        if isinstance(holding, dict)
    ]
    quotes = [
        quote for quote in valuation.get("quotes", []) if isinstance(quote, dict)
    ]
    quote_by_ticker = {
        str(quote.get("canonical_ticker") or quote.get("ticker")): quote
        for quote in quotes
    }

    rows: list[dict[str, Any]] = []
    total_basis = 0.0
    total_current = 0.0
    has_full_current = True
    for holding in holdings:
        quantity = float(holding.get("quantity") or 0)
        avg_buy_price = float(holding.get("avg_buy_price") or 0)
        basis = quantity * avg_buy_price
        total_basis += basis
        ticker = str(holding.get("canonical_ticker") or holding.get("raw_ticker"))
        quote = quote_by_ticker.get(ticker, {})
        current_value = quote.get("position_value")
        if current_value is None:
            has_full_current = False
            numeric_current = None
        else:
            numeric_current = float(current_value)
            total_current += numeric_current
        rows.append(
            {
                "ticker": ticker,
                "asset_class": holding.get("asset_class"),
                "basis_value": basis,
                "current_value": numeric_current,
            }
        )

    denominator = (
        total_current if has_full_current and total_current > 0 else total_basis
    )
    for row in rows:
        value = (
            row["current_value"]
            if row["current_value"] is not None
            else row["basis_value"]
        )
        row["weight"] = (value / denominator * 100) if denominator else 0.0

    rows.sort(key=lambda item: item["weight"], reverse=True)
    top_exposure = rows[:5]
    largest_weight = top_exposure[0]["weight"] if top_exposure else 0.0
    return {
        "total_holdings": len(holdings),
        "invested_amount": total_basis,
        "current_value": (
            total_current if has_full_current else valuation.get("current_value")
        ),
        "unrealized_pnl": valuation.get("unrealized_pnl"),
        "today_pnl": valuation.get("today_pnl"),
        "priced_holdings": valuation.get("priced_holdings", 0),
        "unpriced_holdings": valuation.get("unpriced_holdings", 0),
        "top_exposure": top_exposure,
        "largest_position_weight": largest_weight,
        "concentration_flag": largest_weight >= 25,
    }


def _build_tools(user_id: str) -> tuple[list[Any], dict[str, Any]]:
    from langchain_core.tools import StructuredTool

    def read_portfolio() -> dict[str, Any]:
        """Read the user's imported portfolio holdings."""
        return _read_portfolio(user_id)

    def get_portfolio_valuation() -> dict[str, Any]:
        """Read portfolio valuation using live market quotes where available."""
        return _get_portfolio_valuation()

    def get_market_data(tickers: list[str]) -> dict[str, Any]:
        """Fetch live market quote data for one or more ticker symbols."""
        return _get_market_data(tickers)

    def get_news(ticker: str) -> dict[str, Any]:
        """Fetch recent news articles for a ticker symbol."""
        return _get_news(ticker)

    tools = [
        StructuredTool.from_function(read_portfolio),
        StructuredTool.from_function(get_portfolio_valuation),
        StructuredTool.from_function(get_market_data),
        StructuredTool.from_function(get_news),
        StructuredTool.from_function(run_quant_analysis),
    ]
    return tools, {tool.name: tool for tool in tools}


def _response_type_from_trace(tool_calls: list[dict[str, Any]]) -> str:
    names = {call.get("name") for call in tool_calls}
    if "get_news" in names:
        return "news_digest"
    if "run_quant_analysis" in names:
        return "quant_analysis"
    if "read_portfolio" in names or "get_portfolio_valuation" in names:
        return "portfolio_snapshot"
    return "plain_chat"


def _build_final_response(
    *,
    graph_run_id: str,
    answer: str,
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    unavailable = [
        {"item": call["name"], "reason": call.get("summary", "failed")}
        for call in tool_calls
        if call.get("status") == "failed"
    ]
    deterministic = [
        label
        for label, tool_name in [
            ("portfolio holdings", "read_portfolio"),
            ("portfolio valuation", "get_portfolio_valuation"),
            ("market quotes", "get_market_data"),
            ("ticker news", "get_news"),
            ("quantitative analysis", "run_quant_analysis"),
        ]
        if any(call.get("name") == tool_name for call in tool_calls)
    ]
    response_type = _response_type_from_trace(tool_calls)
    return FinalResponse(
        response_type=response_type,
        bubble_text=answer,
        card_payload={
            "summary": answer,
            "tool_calls": tool_calls,
        },
        confidence_tier="medium" if not unavailable else "low",
        data_quality="good" if not unavailable else "limited",
        retrieval_disclosure={
            "deterministic": deterministic,
            "llm_planned": [
                (
                    f"{call.get('name')}("
                    f"{json.dumps(call.get('args', {}), separators=(',', ':'))})"
                )
                for call in tool_calls
            ],
            "unavailable": unavailable,
        },
        evidence_ids=[],
        assumptions=[],
        principle_conflicts=[],
        graph_run_id=graph_run_id,
    ).model_dump(mode="json")


def _system_prompt() -> str:
    return (
        "You are a portfolio-aware financial analysis assistant. Use tools whenever "
        "the question needs portfolio holdings, market prices, ticker news, or math. "
        "Do not invent holdings, prices, news, or calculations. Use run_quant_analysis "
        "for arithmetic instead of calculating in prose. Keep the final answer concise "
        "and demo-friendly, and mention the tools used. You cannot place trades or "
        "take brokerage actions."
    )


def run_simple_tool_agent(
    *,
    user_id: str,
    user_query: str,
    graph_run_id: str,
) -> Iterator[dict[str, Any]]:
    if not settings.groq_api_key or not settings.groq_model:
        message = (
            "Simple LLM tool mode requires GROQ_API_KEY and GROQ_MODEL to be set."
        )
        yield {
            "event": "node_complete",
            "data": {"node_name": SIMPLE_TOOL_NODES["select_tools"]},
        }
        yield {
            "event": "final",
            "data": {
                "content": message,
                "response": _error_response(message, graph_run_id),
                "tool_calls": [],
                "validation_errors": [],
            },
        }
        return

    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    from langchain_groq import ChatGroq

    tools, tools_by_name = _build_tools(user_id)
    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0,
    ).bind_tools(tools)
    messages: list[Any] = [
        SystemMessage(content=_system_prompt()),
        HumanMessage(content=user_query),
    ]
    tool_calls: list[dict[str, Any]] = []

    yield {
        "event": "node_complete",
        "data": {"node_name": SIMPLE_TOOL_NODES["select_tools"]},
    }
    final_ai_message: Any | None = None
    tool_call_count = 0

    for _index in range(MAX_TOOL_CALLS):
        ai_message = llm.invoke(messages)
        messages.append(ai_message)
        final_ai_message = ai_message
        requested_tool_calls = getattr(ai_message, "tool_calls", []) or []
        if not requested_tool_calls:
            break

        for raw_call in requested_tool_calls:
            if tool_call_count >= MAX_TOOL_CALLS:
                skipped_id = str(
                    raw_call.get("id") or f"skipped-{len(tool_calls) + 1}"
                )
                messages.append(
                    ToolMessage(
                        content=(
                            "Skipped because the simple tool-call limit was reached."
                        ),
                        tool_call_id=skipped_id,
                    )
                )
                continue
            tool_call_count += 1
            name = str(raw_call.get("name", ""))
            args = raw_call.get("args") or {}
            if not isinstance(args, dict):
                args = {}
            tool_call_id = str(raw_call.get("id") or f"{name}-{len(tool_calls) + 1}")
            started = {
                "tool_call_id": tool_call_id,
                "name": name,
                "args": args,
                "status": "started",
                "summary": f"Running {name}",
            }
            yield {"event": "tool_call", "data": started}

            try:
                tool = tools_by_name[name]
                result = tool.invoke(args)
                result_payload = _jsonable(result)
                completed = {
                    "tool_call_id": tool_call_id,
                    "name": name,
                    "args": args,
                    "status": "completed",
                    "summary": _tool_summary(name, result_payload),
                }
                tool_calls.append(completed)
                yield {"event": "tool_call", "data": completed}
                yield {"event": "node_complete", "data": {"node_name": f"tool_{name}"}}
                messages.append(
                    ToolMessage(
                        content=json.dumps(result_payload, default=_json_default),
                        tool_call_id=tool_call_id,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                failed = {
                    "tool_call_id": tool_call_id,
                    "name": name,
                    "args": args,
                    "status": "failed",
                    "summary": str(exc),
                }
                tool_calls.append(failed)
                yield {"event": "tool_call", "data": failed}
                messages.append(
                    ToolMessage(content=str(exc), tool_call_id=tool_call_id)
                )
        if tool_call_count >= MAX_TOOL_CALLS:
            break
    else:
        messages.append(
            HumanMessage(
                content=(
                    "Stop calling tools now and provide the best final answer using "
                    "the tool results already available."
                )
            )
        )
        final_ai_message = llm.invoke(messages)

    yield {
        "event": "node_complete",
        "data": {"node_name": SIMPLE_TOOL_NODES["final_answer"]},
    }
    answer = str(getattr(final_ai_message, "content", "") or "").strip()
    if not answer:
        answer = "I could not produce a final answer from the available tool results."
    yield {
        "event": "final",
        "data": {
            "content": answer,
            "response": _build_final_response(
                graph_run_id=graph_run_id,
                answer=answer,
                tool_calls=tool_calls,
            ),
            "tool_calls": tool_calls,
            "validation_errors": [],
        },
    }
