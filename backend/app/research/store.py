from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal, Any

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.evidence.schemas import EvidenceItem, compute_freshness
from app.models import ResearchArtifact

logger = logging.getLogger(__name__)

# Single collection name for all research artifacts
COLLECTION_NAME = "research_artifacts"

# Initialize Chroma HttpClient client using settings
_client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
_embedding_fn = DefaultEmbeddingFunction()


def get_collection():
    """Get or create the research_artifacts Chroma collection."""
    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_fn,
    )


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
) -> ResearchArtifact:
    """Save a research artifact to Postgres and index it in Chroma.

    This ensures Postgres is the single source of truth, while Chroma acts
    as the queryable vector index for historical retrieval.
    """
    # 1. Save to Postgres
    artifact = ResearchArtifact(
        run_id=run_id,
        artifact_type=artifact_type,
        target=target,
        content_markdown=content_markdown,
        evidence_pack_json=evidence_pack_json,
        recommendation=recommendation,
        confidence_score=confidence_score,
    )
    session.add(artifact)
    await session.flush()  # Populates artifact.id and artifact.created_at

    # 2. Index in Chroma
    # We use a try-except block so that a Chroma indexing failure doesn't roll back the DB transaction.
    try:
        col = get_collection()
        
        # Meta dictionary values must be simple types (str, int, float, bool)
        metadata: dict[str, Any] = {
            "run_id": run_id,
            "artifact_type": artifact_type,
            "target": target or "",
            "id": artifact.id,
            "created_at": artifact.created_at.isoformat(),
        }
        if recommendation:
            metadata["recommendation"] = recommendation
        if confidence_score is not None:
            metadata["confidence_score"] = confidence_score

        col.add(
            ids=[artifact.id],
            documents=[content_markdown],
            metadatas=[metadata],
        )
        logger.info(
            "Indexed research artifact in Chroma | id=%s type=%s target=%s",
            artifact.id,
            artifact_type,
            target,
        )
    except Exception as exc:
        logger.error("Failed to index research artifact in Chroma: %s", exc)

    return artifact


async def search_prior_artifacts(
    query: str,
    *,
    limit: int = 5,
    artifact_type: Literal["macro", "sector", "ticker", "portfolio"] | None = None,
    target: str | None = None,
) -> list[EvidenceItem]:
    """Search historical research artifacts using Chroma vector similarity.

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
