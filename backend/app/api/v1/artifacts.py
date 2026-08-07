from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.services.artifact_service import (
    DEFAULT_ARTIFACT_SERVICE,
    ArtifactValidationError,
)

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_artifact(file: UploadFile = File(...)) -> dict[str, Any]:
    content = await file.read()
    try:
        return DEFAULT_ARTIFACT_SERVICE.create_from_upload(file.filename or "", content)
    except ArtifactValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("")
def list_artifacts() -> dict[str, Any]:
    return {"artifacts": DEFAULT_ARTIFACT_SERVICE.list_artifacts()}


@router.get("/{artifact_id}")
def get_artifact(artifact_id: str) -> dict[str, Any]:
    artifact = DEFAULT_ARTIFACT_SERVICE.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found.",
        )
    return artifact
