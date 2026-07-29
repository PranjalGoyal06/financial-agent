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
from app.portfolio.lib import get_ticker_recommendation
from app.recommend.state import RecommendState
from app.recommend.schemas import RecommendationCard, RecommendEnvelope, RecommendIntent

_provider = YFinanceProvider()

async def parse_input_node(state: RecommendState, config: RunnableConfig) -> dict[str, Any]:
    """Parse the raw message to extract the ticker."""
    messages = state["messages"]
    if not messages:
        return {"error": "No messages provided."}
    
    last_msg = messages[-1].content.replace("/recommend", "").strip()
    
    # Fast path: Check for chips
    chip_match = re.search(r"[\$@]([A-Z0-9.]+)", last_msg)
    if chip_match:
        return {"ticker": chip_match.group(1).upper()}
        
    # Fast path: single word
    words = last_msg.split()
    if len(words) == 1:
        return {"ticker": words[0].upper()}
        
    # Fallback path: LLM extraction
    provider = config.get("configurable", {}).get("llm_provider") or state.get("llm_provider")
    model_name = config.get("configurable", {}).get("llm_model") or state.get("llm_model") or "llama-3.1-8b-instant" if provider == "groq" else None
    
    parser = get_structured_model(
        RecommendIntent, 
        temperature=0.0,
        provider=provider,
        model=model_name
    )
    
    try:
        intent = await parser.ainvoke(last_msg)
        if not intent.ticker:
            return {"error": "Could not identify a ticker. Usage: /recommend [TICKER]"}
        return {"ticker": intent.ticker.upper()}
    except Exception as e:
        return {"error": f"Failed to parse recommendation intent: {e}"}


async def fetch_data_node(state: RecommendState, config: RunnableConfig) -> dict[str, Any]:
    """Fetch market data and prior research for the ticker."""
    ticker = state["ticker"]
    if not ticker:
        return {"error": "Ticker is missing."}
        
    # Fetch data concurrently
    async def get_market_data():
        try:
            quote = await asyncio.to_thread(_provider.get_quote, ticker)
            fundamentals = await asyncio.to_thread(_provider.get_fundamentals, ticker)
            return {
                "quote": quote.model_dump() if quote else None,
                "fundamentals": fundamentals.model_dump() if fundamentals else None
            }
        except Exception as e:
            print(f"Error fetching market data for {ticker}: {e}")
            return None
            
    async def get_prior():
        async for session in get_session():
            return await get_ticker_recommendation(session, ticker)
            
    market_data, prior_research = await asyncio.gather(get_market_data(), get_prior())
    
    if not market_data or not market_data.get("quote"):
        return {"error": f"Failed to fetch market data for {ticker}. Is it a valid symbol?"}
        
    return {
        "market_data": market_data,
        "prior_research": prior_research,
    }


async def generate_card_node(state: RecommendState, config: RunnableConfig) -> dict[str, Any]:
    """Synthesize the real-time data and prior research into a recommendation."""
    ticker = state["ticker"]
    market_data = state["market_data"] or {}
    prior_research = state["prior_research"]

    provider = config["configurable"].get("llm_provider")
    model_name = config["configurable"].get("llm_model")
    
    model = get_structured_model(
        RecommendationCard,
        provider=provider,
        model=model_name,
        temperature=0.0
    )
    
    # Construct context
    quote = market_data.get("quote") or {}
    fundamentals = market_data.get("fundamentals") or {}
    
    context_parts = [
        f"Ticker: {ticker}",
        f"Current Price: {quote.get('current_price')}",
        f"Day Change: {quote.get('day_change_percent')}%",
        f"52w High: {quote.get('fifty_two_week_high')} | Low: {quote.get('fifty_two_week_low')}",
        f"Market Cap: {fundamentals.get('market_cap')}",
        f"P/E Ratio: {fundamentals.get('pe_ratio')}",
        f"Profit Margin: {fundamentals.get('profit_margin')}",
    ]
    
    if prior_research:
        context_parts.append("\n=== Prior Deep Research Found ===")
        context_parts.append(f"Stance: {prior_research.get('recommendation')} (Confidence: {prior_research.get('confidence_score')})")
        context_parts.append(f"Run ID: {prior_research.get('run_id')}")

    prompt = f"""You are PAISA, an elite quantitative portfolio manager.
Analyze the following data for {ticker} and provide an instant recommendation.

DATA CONTEXT:
{chr(10).join(context_parts)}

INSTRUCTIONS:
1. Provide a recommendation: 'Buy', 'Hold', 'Sell', or 'Avoid'.
2. Provide a 2-3 sentence punchy rationale for this stance. If prior deep research exists, lean heavily on it but contextualize it with today's price action.
3. Assign a confidence score from 0.0 to 1.0.
4. Set 'based_on_prior_research' to true ONLY IF prior deep research was provided in the context.
5. Set 'run_id' to the Run ID from prior research if it exists, otherwise omit.
"""
    
    try:
        card: RecommendationCard = await model.ainvoke(prompt)
        envelope = RecommendEnvelope(card=card)
        return {"envelope": envelope}
    except Exception as exc:
        return {"error": f"Failed to generate recommendation: {exc!s}"}


async def audit_persist_node(state: RecommendState, config: RunnableConfig) -> dict[str, Any]:
    """Log the recommendation event."""
    envelope = state.get("envelope")
    if not envelope:
        return {}
        
    try:
        async for session in get_session():
            audit_event = AuditEventModel(
                request_id=config.get("configurable", {}).get("request_id", "unknown"),
                command="recommend",
                model_provider=config.get("configurable", {}).get("llm_provider", "unknown"),
                model_name=config.get("configurable", {}).get("llm_model", "unknown"),
                run_mode="chat",
                payload_json=json.dumps(envelope.model_dump())
            )
            session.add(audit_event)
            await session.commit()
    except Exception as e:
        print(f"Failed to log audit event: {e}")
        
    ticker = state.get("ticker", "asset")
    from langchain_core.messages import AIMessage
    
    return {
        "messages": [AIMessage(content=f"[Rendered Recommendation Card for {ticker}]")]
    }
