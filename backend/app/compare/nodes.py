import asyncio
import re
import json
from datetime import datetime, timezone
from typing import Any
from langchain_core.runnables import RunnableConfig

from app.db import get_session
from app.models import AuditEventModel
from app.llm.provider import get_structured_model
from app.market_data.provider import YFinanceProvider
from app.market_data.tools import (
    get_quote_tool,
    get_historical_data_tool,
    get_fundamentals_tool,
)
from app.compare.state import CompareState
from app.compare.schemas import ComparisonIntent, ComparisonCard, CardEnvelope

_provider = YFinanceProvider()

async def parse_input_node(state: CompareState, config: RunnableConfig) -> dict[str, Any]:
    """Parse the raw message into exactly two tickers and an optional focus."""
    messages = state["messages"]
    if not messages:
        return {"error": "No messages provided."}
    
    last_msg = messages[-1].content.replace("/compare", "").strip()
    
    # Fast path: Check for chips
    # Assume chips are either Notion style @TICKER or $TICKER
    # We'll look for strings matching $[A-Z0-9.]+ or @[A-Z0-9.]+
    chip_matches = re.findall(r"[\$@]([A-Z0-9.]+)", last_msg)
    
    # Deduplicate while preserving order
    seen = set()
    chips = [x for x in chip_matches if not (x in seen or seen.add(x))]
    
    if len(chips) == 2:
        # We got exactly two chips, fast path wins. 
        # Strip chips from message to find focus
        focus_text = re.sub(r"[\$@][A-Z0-9.]+", "", last_msg).strip()
        focus = focus_text if len(focus_text) > 3 else None
        return {"tickers": chips, "focus": focus}
        
    # Fallback path: LLM extraction
    # Since role-based factory is missing, we'll explicitly use the cheap model
    # (or whatever is configured). 
    provider = state.get("llm_provider")
    model = state.get("llm_model") or "llama-3.1-8b-instant" if provider == "groq" else None
    
    parser = get_structured_model(
        ComparisonIntent, 
        temperature=0.0,
        provider=provider,
        model=model
    )
    
    try:
        # We invoke this as a tool conceptually, but it's just parsing.
        intent = await parser.ainvoke(last_msg, config)
        if len(intent.tickers) != 2:
            return {"error": f"I need exactly two tickers to compare. Found: {intent.tickers}"}
        return {"tickers": intent.tickers, "focus": intent.focus}
    except Exception as e:
        return {"error": f"Failed to parse comparison intent: {e}"}


async def _fetch_for_ticker(ticker: str, config: RunnableConfig) -> dict[str, Any]:
    """Fetch all symmetric data for a single ticker."""
    # We call the existing tools so that LangChain callbacks emit tool_call events
    # which the UI uses to show loading spinners.
    
    quote_task = get_quote_tool.ainvoke({"ticker": ticker}, config)
    hist_task = get_historical_data_tool.ainvoke({"ticker": ticker, "period": "1y", "interval": "1d"}, config)
    fund_task = get_fundamentals_tool.ainvoke({"ticker": ticker}, config)
    
    # If quote fails, we want it to bubble up to abort the comparison.
    try:
        quote = await quote_task
        # Quick validation that we got a valid quote
        if "error" in quote.lower() or "not found" in quote.lower():
            raise ValueError(f"Failed to fetch quote for {ticker}")
    except Exception as e:
        raise ValueError(f"Aborting comparison: Could not fetch quote for {ticker}. ({e})")
        
    # Others can fail softly
    try:
        hist = await hist_task
    except Exception:
        hist = "{}"
        
    try:
        fund = await fund_task
    except Exception:
        fund = "{}"
        
    return {
        "quote": quote,
        "historical": hist,
        "fundamentals": fund
    }

async def fetch_data_node(state: CompareState, config: RunnableConfig) -> dict[str, Any]:
    """Fetch quote, historical, and fundamentals in parallel for both tickers."""
    if state.get("error"):
        return {}
        
    tickers = state["tickers"]
    
    try:
        t1_res, t2_res = await asyncio.gather(
            _fetch_for_ticker(tickers[0], config),
            _fetch_for_ticker(tickers[1], config)
        )
    except Exception as e:
        return {"error": str(e)}
        
    return {
        "market_data": {
            tickers[0]: t1_res,
            tickers[1]: t2_res
        }
    }


async def generate_comparison_node(state: CompareState, config: RunnableConfig) -> dict[str, Any]:
    """Generate the structured comparison card."""
    if state.get("error"):
        return {}
        
    tickers = state["tickers"]
    focus = state.get("focus")
    market_data = state["market_data"]
    
    provider = state.get("llm_provider")
    model = state.get("llm_model")
    
    generator = get_structured_model(
        ComparisonCard,
        temperature=0.1,
        provider=provider,
        model=model
    )
    
    prompt = f"""
    You are an expert financial analyst. Please compare the following two stocks: {tickers[0]} and {tickers[1]}.
    Focus on: {focus or 'overall fundamentals, recent performance, and valuation.'}
    
    Data for {tickers[0]}:
    {json.dumps(market_data[tickers[0]])}
    
    Data for {tickers[1]}:
    {json.dumps(market_data[tickers[1]])}
    
    Generate a structured ComparisonCard evaluating these two assets symmetrically.
    For each dimension, state which asset has the stronger profile (lean), or if it's neutral.
    
    IMPORTANT: You must output ONLY valid, raw JSON matching the required schema. Do not output markdown tables, do not output markdown code blocks (```json), and do not include any conversational text. Return ONLY the raw JSON object.
    """
    
    try:
        card = await generator.ainvoke(prompt, config)
        # Enforce exact tickers output
        card.tickers = tickers
        
        envelope = CardEnvelope(
            command="compare",
            request_id=state["request_id"],
            generated_at=datetime.now(timezone.utc).isoformat(),
            model_provider=provider or "default",
            model_name=model or "default",
            run_mode="interactive",
            payload=card.model_dump()
        )
        return {"envelope": envelope}
    except Exception as e:
        return {"error": f"Failed to generate comparison: {e}"}


async def audit_persist_node(state: CompareState, config: RunnableConfig) -> dict[str, Any]:
    """Persist the event to the audit_events table."""
    envelope = state.get("envelope")
    if not envelope:
        return {}
        
    async for session in get_session():
        audit = AuditEventModel(
            request_id=envelope.request_id,
            command=envelope.command,
            model_provider=envelope.model_provider,
            model_name=envelope.model_name,
            run_mode=envelope.run_mode,
            payload_json=json.dumps(envelope.payload),
            evidence_ids="[]"
        )
        session.add(audit)
        await session.commit()
        break # get_session is a generator
        
    return {}
