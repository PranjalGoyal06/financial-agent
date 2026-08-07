from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(slots=True)
class ArtifactRecord:
    title: str
    filename: str
    artifact_type: str
    content: str
    user_id: str = "demo-user"
    artifact_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ArtifactsRepository:
    def __init__(self) -> None:
        self._artifacts: list[ArtifactRecord] = []

    def insert(self, record: ArtifactRecord) -> ArtifactRecord:
        self._artifacts.append(record)
        return record

    def list_by_user(self, user_id: str) -> list[ArtifactRecord]:
        return [artifact for artifact in self._artifacts if artifact.user_id == user_id]

    def get_by_id(self, artifact_id: str, user_id: str) -> ArtifactRecord | None:
        for artifact in self._artifacts:
            if artifact.artifact_id == artifact_id and artifact.user_id == user_id:
                return artifact
        return None

    def clear(self) -> None:
        self._artifacts.clear()


DEFAULT_ARTIFACTS_REPOSITORY = ArtifactsRepository()
