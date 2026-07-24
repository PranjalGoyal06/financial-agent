from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from typing import Literal, Any

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.evidence.schemas import EvidenceItem, compute_freshness
from app.models import Artifact

logger = logging.getLogger(__name__)

# Single collection name for all artifacts
COLLECTION_NAME = "artifacts"

# Initialize Chroma HttpClient client using settings
_client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
_embedding_fn = DefaultEmbeddingFunction()


def get_collection():
    """Get or create the artifacts Chroma collection."""
    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_fn,
    )


async def save_artifact(
    session: AsyncSession,
    *,
    source_type: str,
    source_ref_id: str | None = None,
    title: str,
    content_markdown: str,
    tags: list[str] | None = None,
    metadata_json: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> Artifact:
    """Save a generalized artifact to Postgres and index it in Chroma.

    This ensures Postgres is the single source of truth, while Chroma acts
    as the queryable vector index for historical retrieval.
    """
    if tags is None:
        tags = []
    if metadata_json is None:
        metadata_json = {}

    # 1. Save to Postgres
    artifact = Artifact(
        source_type=source_type,
        source_ref_id=source_ref_id,
        title=title,
        content_markdown=content_markdown,
        tags=json.dumps(tags),
        metadata_json=json.dumps(metadata_json),
        user_id=user_id,
    )
    session.add(artifact)
    await session.flush()  # Populates artifact.id and artifact.created_at

    # 2. Index in Chroma
    # We use a try-except block so that a Chroma indexing failure doesn't roll back the DB transaction.
    try:
        col = get_collection()
        
        # Meta dictionary values must be simple types (str, int, float, bool)
        metadata: dict[str, Any] = {
            "source_type": source_type,
            "id": artifact.id,
            "created_at": artifact.created_at.isoformat(),
        }
        if source_ref_id:
            metadata["source_ref_id"] = source_ref_id
            
        # Push flat metadata for filtering
        for k, v in metadata_json.items():
            if isinstance(v, (str, int, float, bool)):
                metadata[k] = v

        col.add(
            ids=[artifact.id],
            documents=[content_markdown],
            metadatas=[metadata],
        )
        logger.info(
            "Indexed artifact in Chroma | id=%s source_type=%s",
            artifact.id,
            source_type,
        )
        
        # Mark as indexed in DB (optional, but good practice)
        artifact.chroma_indexed = True
        session.add(artifact)
        await session.flush()

    except Exception as exc:
        logger.error("Failed to index artifact in Chroma: %s", exc)

    return artifact


async def delete_artifact(session: AsyncSession, artifact_id: str) -> bool:
    """Delete an artifact from Postgres and Chroma."""
    # 1. Delete from Postgres
    artifact = await session.get(Artifact, artifact_id)
    if not artifact:
        return False
        
    await session.delete(artifact)
    await session.flush()
    
    # 2. Delete from Chroma
    try:
        col = get_collection()
        col.delete(ids=[artifact_id])
    except Exception as exc:
        logger.warning("Failed to delete artifact from Chroma: %s", exc)
        
    return True


async def rename_artifact(session: AsyncSession, artifact_id: str, new_title: str) -> Artifact | None:
    """Rename an artifact's title in Postgres."""
    artifact = await session.get(Artifact, artifact_id)
    if not artifact:
        return None
        
    artifact.title = new_title
    await session.flush()
    
    # Chroma index doesn't currently include the title in metadata or documents
    # in a way that requires an update for simple renaming, so we just update Postgres.
    
    return artifact


async def save_research_artifact(
    session: AsyncSession,
    *,
    run_id: str,
    artifact_type: Literal["macro", "sector", "ticker", "portfolio"],
    target: str | None,
    content_markdown: str,
    evidence_pack_json: str,
    recommendation: str | None = None,
    confidence_score: int | None = None,
) -> Artifact:
    """Wrapper to save research-specific artifacts using the generalized schema."""
    title = f"{artifact_type.capitalize()} Research"
    if target:
        title += f" for {target}"

    tags = [f"type:{artifact_type}"]
    if target:
        tags.append(f"target:{target}")

    metadata = {
        "artifact_type": artifact_type,
        "target": target,
        "evidence_pack_json": evidence_pack_json,
    }
    if recommendation:
        metadata["recommendation"] = recommendation
        tags.append(f"recommendation:{recommendation}")
    if confidence_score is not None:
        metadata["confidence_score"] = confidence_score

    return await save_artifact(
        session=session,
        source_type="research",
        source_ref_id=run_id,
        title=title,
        content_markdown=content_markdown,
        tags=tags,
        metadata_json=metadata,
    )


async def search_prior_artifacts(
    query: str,
    *,
    limit: int = 5,
    artifact_type: Literal["macro", "sector", "ticker", "portfolio"] | None = None,
    target: str | None = None,
) -> list[EvidenceItem]:
    """Search historical artifacts using Chroma vector similarity.

    Returns the matches normalised to EvidenceItem objects of type
    ``prior_artifact``, ready to be fed into downstream nodes.
    """
    try:
        col = get_collection()
        
        # Build metadata filters
        where_clause: dict[str, Any] = {}
        if artifact_type:
            where_clause["artifact_type"] = artifact_type
        if target:
            where_clause["target"] = target

        kwargs = {}
        if where_clause:
            # If only one filter key exists, Chroma expects the dict directly.
            # Otherwise, use an $and operator.
            if len(where_clause) == 1:
                kwargs["where"] = where_clause
            else:
                kwargs["where"] = {"$and": [{k: v} for k, v in where_clause.items()]}

        results = col.query(
            query_texts=[query],
            n_results=limit,
            **kwargs,
        )

        evidence_items = []
        fetched_at = datetime.now(timezone.utc)

        # Parse Chroma query outputs
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        for idx, doc in enumerate(documents):
            meta = metadatas[idx]
            created_at_str = meta.get("created_at")
            published_at = None
            if created_at_str:
                try:
                    published_at = datetime.fromisoformat(created_at_str)
                except ValueError:
                    pass

            item_id = f"prior_{ids[idx][:8]}"
            evidence_items.append(
                EvidenceItem(
                    id=item_id,
                    type="prior_artifact",
                    source="chroma_retrieval",
                    published_at=published_at,
                    fetched_at=fetched_at,
                    freshness=compute_freshness(published_at, fetched_at),
                    summary=(
                        f"Prior research ({meta.get('artifact_type', 'unknown')} "
                        f"target={meta.get('target', 'N/A')} created={created_at_str}):\n{doc}"
                    ),
                )
            )

        return evidence_items

    except Exception as exc:
        logger.error("Failed to query prior artifacts in Chroma: %s", exc)
        return []
