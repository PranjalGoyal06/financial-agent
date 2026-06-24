from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(slots=True)
class WatchlistItemRecord:
    user_id: str
    ticker: str
    exchange: str
    notes: str = ""
    watchlist_item_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WatchlistRepository:
    def __init__(self) -> None:
        self._items: list[WatchlistItemRecord] = []

    def list_by_user(self, user_id: str) -> list[WatchlistItemRecord]:
        return [item for item in self._items if item.user_id == user_id]

    def insert(self, record: WatchlistItemRecord) -> None:
        self._items.append(record)


DEFAULT_WATCHLIST_REPOSITORY = WatchlistRepository()
