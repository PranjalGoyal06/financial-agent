from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class GreetingData(BaseModel):
    greeting: str
    market_status: Literal["open", "closed"]
    market_closed_relative_time: str
    research_run_relative_time: str
    tickers_analyzed: int


class Metric(BaseModel):
    price: float | None = None
    day_change_pct: float | None = None


class VixMetric(BaseModel):
    value: float | None = None
    tier: Literal["low", "moderate", "elevated", "high", "unknown"]


class Breadth(BaseModel):
    advancers: int
    decliners: int
    unchanged: int


class PortfolioNetPnl(BaseModel):
    amount: float
    pct: float


class ClimateData(BaseModel):
    nifty50: Metric
    india_vix: VixMetric
    holdings_breadth: Breadth
    portfolio_net_pnl: PortfolioNetPnl
    fetched_at: str


class ActionCard(BaseModel):
    ticker: str
    recommendation: str
    confidence_score: int
    confidence_tier: Literal["high", "moderate", "low", "unknown"]
    headline: str
    bear_case_snippet: str
    change_context: str | None = None
    run_id: str


class ActionDeskData(BaseModel):
    cards: list[ActionCard]
    total_qualifying: int
    has_overflow: bool


class NoActionData(BaseModel):
    count: int
    total_reviewed: int


class NewsItem(BaseModel):
    id: str
    title: str
    url: str
    source: str
    published_at: str
    target: str
    summary: str


class BriefingResponse(BaseModel):
    greeting: GreetingData
    climate: ClimateData
    action_desk: ActionDeskData
    no_action: NoActionData
    top_news: list[NewsItem]
