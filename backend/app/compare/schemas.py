from __future__ import annotations

from typing import Any, Literal, Union
from pydantic import BaseModel, Field


class ComparisonCardRow(BaseModel):
    dimension: str = Field(description='e.g., "3M Momentum", "P/E", "Volatility"')
    value_a: str | None = None
    value_b: str | None = None
    lean: Literal["A", "B", "neutral", "insufficient_data"] = Field(description="Which ticker wins, or neutral, or not enough data")
    note: str = Field(description="Cited justification")


class ComparisonCard(BaseModel):
    tickers: list[str] = Field(min_length=2, max_length=2)
    rows: list[ComparisonCardRow]
    overall_summary: str
    confidence_tier: str
    evidence_ids: list[str] = Field(default_factory=list)


class CardEnvelope(BaseModel):
    command: Literal["compare", "recommend", "research", "create_artifact"]
    request_id: str
    generated_at: str
    model_provider: str
    model_name: str
    run_mode: Literal["interactive", "batch"]
    payload: dict[str, Any]


class ComparisonIntent(BaseModel):
    tickers: list[str] = Field(description="Exactly two tickers found in the user message.")
    focus: str | None = Field(description="Specific focus or criteria for comparison, if any.")
