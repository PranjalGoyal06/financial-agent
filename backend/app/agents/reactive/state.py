from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict

DataQualityVerdict = Literal[
    "ok", "degraded", "good", "limited", "stale", "critical_failure"
]


class ReactiveState(TypedDict):
    session_id: str
    graph_run_id: str
    user_id: str
    user_query: str
    user_profile: dict[str, Any]
    portfolio: dict[str, Any]
    watchlist: list[dict[str, Any]]
    principles: list[dict[str, Any]]
    investment_principles: list[dict[str, Any]]
    recent_chat_context: list[dict[str, Any]]
    data_freshness_status: dict[str, Any]
    retrieval_plan: dict[str, Any]
    retrieval_disclosure: dict[str, Any]
    relevant_tickers: list[str]
    market_data: dict[str, Any]
    retrieved_chunks: list[dict[str, Any]]
    evidence_pack: list[dict[str, Any]]
    prior_recommendations: list[dict[str, Any]]
    data_quality: dict[str, Any]
    data_quality_verdict: DataQualityVerdict
    data_quality_passed: bool
    data_quality_flags: list[str]
    compressed_context: str
    principle_conflicts: list[dict[str, Any]]
    raw_analysis: str
    llm_raw_output: str
    parsed_output: dict[str, Any]
    recommendation: dict[str, Any]
    validation_errors: list[str]
    final_response: dict[str, Any]
    audit_events: list[dict[str, Any]]
    messages: Annotated[list[dict[str, Any]], add]
    reasoning_trace: Annotated[list[dict[str, Any]], add]
