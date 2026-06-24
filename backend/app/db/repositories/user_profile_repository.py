from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(slots=True)
class UserProfileRecord:
    user_id: str
    risk_tolerance: str
    investment_horizon: str
    currency_base: str
    profile_id: str = field(default_factory=lambda: str(uuid4()))
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UserProfileRepository:
    def __init__(self) -> None:
        self._profiles: dict[str, UserProfileRecord] = {}

    def get_by_user(self, user_id: str) -> UserProfileRecord | None:
        return self._profiles.get(user_id)

    def upsert(self, record: UserProfileRecord) -> None:
        self._profiles[record.user_id] = record


DEFAULT_USER_PROFILE_REPOSITORY = UserProfileRepository()
