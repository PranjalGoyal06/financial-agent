from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class AuditEvent:
    event_id: str
    event_type: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


AUDIT_EVENTS: list[AuditEvent] = []


def log_event(event_type: str, message: str, details: dict[str, Any] | None = None) -> AuditEvent:
    event = AuditEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        message=message,
        details=details or {},
    )
    AUDIT_EVENTS.append(event)
    return event


def record(event_type: str, message: str, details: dict[str, Any] | None = None) -> AuditEvent:
    return log_event(event_type, message, details)

