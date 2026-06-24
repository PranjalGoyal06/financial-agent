from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.services import audit_service


class AuditRepository:
    def insert_many(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            audit_service.log_event(
                str(event.get("event_type", "reactive.audit_event")),
                str(
                    event.get(
                        "message", event.get("event_type", "Reactive audit event.")
                    )
                ),
                dict(event),
            )

    def list_all(self) -> list[dict[str, Any]]:
        return [asdict(event) for event in audit_service.AUDIT_EVENTS]

    def clear(self) -> None:
        audit_service.AUDIT_EVENTS.clear()


DEFAULT_AUDIT_REPOSITORY = AuditRepository()
