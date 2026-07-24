from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.config import settings
from app.db import get_session
from app.models import Artifact
from app.research.store import save_artifact, delete_artifact, rename_artifact

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/artifacts", tags=["Artifacts"])


class ArtifactCreate(BaseModel):
    title: str
    content_markdown: str
    tags: list[str] = []
    metadata_json: dict[str, Any] = {}
    source_type: str = "user_upload"


class ArtifactUpdate(BaseModel):
    title: str | None = None


@router.get("")
async def list_artifacts(
    source_type: str | None = None,
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session),
) -> dict[str, list[dict[str, Any]]]:
    """Retrieve all artifacts, optionally filtered by source_type."""
    stmt = select(Artifact).order_by(Artifact.created_at.desc())
    
    if source_type:
        stmt = stmt.where(Artifact.source_type == source_type)

    res = await session.execute(stmt)
    artifacts = res.scalars().all()

    items = []
    for a in artifacts:
        items.append({
            "id": a.id,
            "title": a.title,
            "source_type": a.source_type,
            "source_ref_id": a.source_ref_id,
            "content_markdown": a.content_markdown,
            "tags": json.loads(a.tags) if a.tags else [],
            "metadata_json": json.loads(a.metadata_json) if a.metadata_json else {},
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })

    return {"artifacts": items}


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_artifact(
    artifact_in: ArtifactCreate,
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Upload a manually created artifact."""
    
    # Save the artifact using the same function that indexes to Chroma
    artifact = await save_artifact(
        session=session,
        source_type=artifact_in.source_type,
        title=artifact_in.title,
        content_markdown=artifact_in.content_markdown,
        tags=artifact_in.tags,
        metadata_json=artifact_in.metadata_json,
        user_id=user_id,
    )
    
    return {
        "id": artifact.id,
        "title": artifact.title,
        "status": "created"
    }


@router.delete("/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artifact_endpoint(
    artifact_id: str,
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an artifact by ID."""
    success = await delete_artifact(session, artifact_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found."
        )


@router.patch("/{artifact_id}")
async def rename_artifact_endpoint(
    artifact_id: str,
    artifact_update: ArtifactUpdate,
    user_id: str = settings.default_user_id,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Rename or update an artifact."""
    if not artifact_update.title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update provided."
        )
        
    artifact = await rename_artifact(session, artifact_id, artifact_update.title)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found."
        )
        
    return {
        "id": artifact.id,
        "title": artifact.title,
        "status": "updated"
    }

