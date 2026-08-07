from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

RetrievalIntent = Literal[
    "general_question",
    "portfolio_explanation",
    "recommendation",
    "comparison",
    "risk_analysis",
    "news_impact",
    "research_followup",
    "data_request",
    "research_run_trigger",
    "unclear",
]

SourceType = Literal[
    "market_quote",
    "news",
    "artifact",
    "portfolio",
    "allocation",
    "recommendation",
    "fundamental",
]

QualityTier = Literal["fresh", "stale", "limited", "unavailable"]
DataQualityOverall = Literal["good", "limited", "stale", "critical_failure"]
ConfidenceTier = Literal["high", "medium", "low", "insufficient"]
ResponseType = Literal[
    "plain_chat",
    "recommendation",
    "news_digest",
    "comparison",
    "portfolio_snapshot",
    "technical_analysis",
    "fundamental_analysis",
    "quant_analysis",
    "research_run_status",
    "insufficient_data",
    "error",
]


class RetrievalPlan(BaseModel):
    intent: RetrievalIntent
    relevant_tickers: list[str] = Field(default_factory=list)
    reason_for_retrieval: str = ""
    warnings: list[str] = Field(default_factory=list)
    retrieval_items: list[str] = Field(default_factory=list)
    external_tickers: list[str] = Field(default_factory=list)

    @field_validator("relevant_tickers", "external_tickers", mode="before")
    @classmethod
    def _normalise_ticker_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        return [str(item).strip().upper() for item in value if str(item).strip()]


class EvidenceItem(BaseModel):
    evidence_id: str
    source_type: SourceType
    ticker: str | None = None
    provider: str
    fetched_at: datetime
    quality_tier: QualityTier
    payload: dict[str, Any] = Field(default_factory=dict)
    failure_reason: str | None = None


class RetrievalDisclosure(BaseModel):
    deterministic: list[str] = Field(default_factory=list)
    llm_planned: list[str] = Field(default_factory=list)
    unavailable: list[dict[str, str]] = Field(default_factory=list)


class DataQualityReport(BaseModel):
    overall: DataQualityOverall
    missing_critical: list[str] = Field(default_factory=list)
    stale_items: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RecommendationCard(BaseModel):
    action: str
    summary: str
    confidence_tier: ConfidenceTier
    data_quality: DataQualityOverall | str
    bear_case: str
    key_risks: list[str] = Field(default_factory=list)
    no_action_case: str
    assumptions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class NewsDigestCard(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)
    summary: str
    data_quality: DataQualityOverall | str
    caveats: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ComparisonCard(BaseModel):
    tickers: list[str]
    metrics: dict[str, Any] = Field(default_factory=dict)
    summary: str
    risk_notes: list[str] = Field(default_factory=list)
    data_quality: DataQualityOverall | str
    caveats: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class PortfolioSnapshotCard(BaseModel):
    total_holdings: int
    allocation: list[dict[str, Any]] = Field(default_factory=list)
    concentration: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    suggested_prompts: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ResearchRunStatusCard(BaseModel):
    status: Literal["not_started", "unavailable", "ready"]
    message: str
    next_action: str


class InsufficientDataCard(BaseModel):
    missing: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ErrorCard(BaseModel):
    message: str
    recoverable: bool = True


CARD_MODELS: dict[str, type[BaseModel]] = {
    "recommendation": RecommendationCard,
    "news_digest": NewsDigestCard,
    "comparison": ComparisonCard,
    "portfolio_snapshot": PortfolioSnapshotCard,
    "research_run_status": ResearchRunStatusCard,
    "insufficient_data": InsufficientDataCard,
    "error": ErrorCard,
}


class LLMOutput(BaseModel):
    response_type: ResponseType
    bubble_text: str
    card_payload: dict[str, Any] | None = None
    evidence_ids_used: list[str] = Field(default_factory=list)
    confidence_tier: ConfidenceTier
    assumptions: list[str] = Field(default_factory=list)
    principle_conflicts: list[str] = Field(default_factory=list)


class FinalResponse(BaseModel):
    response_type: str
    bubble_text: str
    card_payload: dict[str, Any] | None = None
    confidence_tier: str
    data_quality: str
    retrieval_disclosure: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    principle_conflicts: list[str] = Field(default_factory=list)
    advisory_only: bool = True
    graph_run_id: str


def model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)
