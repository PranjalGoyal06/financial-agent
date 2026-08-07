from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(slots=True)
class InvestmentPrincipleRecord:
    user_id: str
    title: str
    body: str
    priority: int
    is_active: bool = True
    principle_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InvestmentPrinciplesRepository:
    def __init__(self) -> None:
        self._principles: list[InvestmentPrincipleRecord] = []

    def list_active_by_user(self, user_id: str) -> list[InvestmentPrincipleRecord]:
        return [
            principle
            for principle in self._principles
            if principle.user_id == user_id and principle.is_active
        ]

    def insert_many(self, records: list[InvestmentPrincipleRecord]) -> None:
        self._principles.extend(records)


DEFAULT_INVESTMENT_PRINCIPLES_REPOSITORY = InvestmentPrinciplesRepository()
