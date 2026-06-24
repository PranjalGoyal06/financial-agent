from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class RecommendationRecord:
    user_id: str
    source_type: str
    source_id: str
    action: str
    confidence_tier: str
    data_quality: str
    summary: str
    card_payload: dict[str, Any] = field(default_factory=dict)
    recommendation_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class RecommendationsRepository:
    def __init__(self) -> None:
        self._recommendations: list[RecommendationRecord] = []

    def insert(self, record: RecommendationRecord) -> RecommendationRecord:
        self._recommendations.append(record)
        return record

    def list_by_user(self, user_id: str) -> list[RecommendationRecord]:
        return [
            recommendation
            for recommendation in self._recommendations
            if recommendation.user_id == user_id
        ]

    def list_by_tickers(
        self, user_id: str, tickers: list[str]
    ) -> list[RecommendationRecord]:
        ticker_set = set(tickers)
        results: list[RecommendationRecord] = []
        for recommendation in self.list_by_user(user_id):
            payload_tickers = recommendation.card_payload.get("tickers", [])
            if isinstance(payload_tickers, list) and ticker_set.intersection(
                str(ticker).upper() for ticker in payload_tickers
            ):
                results.append(recommendation)
        return results

    def clear(self) -> None:
        self._recommendations.clear()


DEFAULT_RECOMMENDATIONS_REPOSITORY = RecommendationsRepository()
