from typing import TypedDict
from langchain_core.messages import AnyMessage

from app.recommend.schemas import RecommendEnvelope

class RecommendState(TypedDict):
    messages: list[AnyMessage]
    ticker: str | None
    market_data: dict | None
    prior_research: dict | None
    envelope: RecommendEnvelope | None
    error: str | None
