from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


CACHE: dict[str, "CacheEntry"] = {}


@dataclass(slots=True)
class CacheEntry:
    value: Any
    fetched_at: datetime
    ttl_seconds: int

    @property
    def is_stale(self) -> bool:
        age = (datetime.now(timezone.utc) - self.fetched_at).total_seconds()
        return age >= self.ttl_seconds


def get(key: str) -> tuple[Any, bool]:
    entry = CACHE.get(key)
    if entry is None:
        return None, True
    return entry.value, entry.is_stale


def set(key: str, value: Any, ttl_seconds: int = 900) -> None:
    CACHE[key] = CacheEntry(
        value=value,
        fetched_at=datetime.now(timezone.utc),
        ttl_seconds=ttl_seconds,
    )

