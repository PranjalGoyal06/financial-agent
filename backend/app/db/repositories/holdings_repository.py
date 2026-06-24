from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(slots=True)
class HoldingRecord:
    user_id: str
    raw_ticker: str
    canonical_ticker: str
    exchange: str
    asset_class: str
    quantity: float
    avg_buy_price: float
    currency: str
    purchase_date: str
    portfolio_import_id: str | None = None
    holding_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class HoldingsRepository:
    def __init__(self) -> None:
        self._holdings: list[HoldingRecord] = []

    def list_all(self) -> list[HoldingRecord]:
        return list(self._holdings)

    def list_by_user(self, user_id: str) -> list[HoldingRecord]:
        return [holding for holding in self._holdings if holding.user_id == user_id]

    def insert_many(self, records: list[HoldingRecord]) -> None:
        snapshot = list(self._holdings)
        try:
            for record in records:
                self._holdings.append(record)
        except Exception:
            self._holdings = snapshot
            raise

    def replace_for_user(self, user_id: str, records: list[HoldingRecord]) -> None:
        snapshot = list(self._holdings)
        try:
            self._holdings = [
                holding for holding in self._holdings if holding.user_id != user_id
            ]
            self._holdings.extend(records)
        except Exception:
            self._holdings = snapshot
            raise

    def clear(self) -> None:
        self._holdings.clear()


DEFAULT_HOLDINGS_REPOSITORY = HoldingsRepository()
