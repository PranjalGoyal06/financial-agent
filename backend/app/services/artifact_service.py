from __future__ import annotations

from dataclasses import asdict
from pathlib import PurePath
from typing import Any

from app.db.repositories.artifacts_repository import (
    DEFAULT_ARTIFACTS_REPOSITORY,
    ArtifactRecord,
    ArtifactsRepository,
)

ALLOWED_ARTIFACT_EXTENSIONS = {".md", ".txt"}
PREVIEW_LENGTH = 240


class ArtifactValidationError(ValueError):
    pass


class ArtifactService:
    def __init__(
        self,
        repository: ArtifactsRepository | None = None,
        user_id: str = "demo-user",
    ) -> None:
        self.repository = repository or DEFAULT_ARTIFACTS_REPOSITORY
        self.user_id = user_id

    def create_from_upload(self, filename: str, content_bytes: bytes) -> dict[str, Any]:
        path = PurePath(filename or "")
        suffix = path.suffix.lower()
        if suffix not in ALLOWED_ARTIFACT_EXTENSIONS:
            raise ArtifactValidationError(
                "Only .txt and .md knowledge artifacts are supported."
            )

        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ArtifactValidationError(
                "Knowledge artifacts must be UTF-8 text."
            ) from exc

        title = path.stem or filename
        record = self.repository.insert(
            ArtifactRecord(
                title=title,
                filename=filename,
                artifact_type=suffix.lstrip("."),
                content=content,
                user_id=self.user_id,
            )
        )
        return self.to_detail(record)

    def list_artifacts(self) -> list[dict[str, Any]]:
        return [
            self.to_summary(artifact)
            for artifact in self.repository.list_by_user(self.user_id)
        ]

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        record = self.repository.get_by_id(artifact_id, self.user_id)
        if record is None:
            return None
        return self.to_detail(record)

    @staticmethod
    def to_summary(record: ArtifactRecord) -> dict[str, Any]:
        summary = asdict(record)
        content = summary.pop("content")
        summary["preview"] = _preview(content)
        return summary

    @staticmethod
    def to_detail(record: ArtifactRecord) -> dict[str, Any]:
        detail = asdict(record)
        detail["preview"] = _preview(record.content)
        return detail


def _preview(content: str) -> str:
    compact = " ".join(content.split())
    if len(compact) <= PREVIEW_LENGTH:
        return compact
    return f"{compact[:PREVIEW_LENGTH].rstrip()}..."


DEFAULT_ARTIFACT_SERVICE = ArtifactService()
