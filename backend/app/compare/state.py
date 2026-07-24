from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage

from app.compare.schemas import CardEnvelope


class CompareState(TypedDict):
    messages: list[AnyMessage]
    request_id: str
    llm_provider: str
    llm_model: str
    
    # extracted info
    tickers: list[str]
    focus: str | None
    
    # fetched data
    market_data: dict[str, dict[str, Any]]
    
    # Generated card
    envelope: CardEnvelope | None
    
    # Error state
    error: str | None
