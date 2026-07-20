from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SearchResult(BaseModel):
    """Raw Tavily search result before normalization to EvidenceItem.

    Kept as an intermediate type so the mapping step is testable in
    isolation and future providers (e.g. Perplexity) can supply the
    same shape.
    """

    title: str
    url: str
    content: str          # clean snippet text; no HTML
    published_date: str | None = None   # Tavily string, e.g. "2024-01-15T10:30:00"
    score: float = 0.0    # Tavily relevance score (0–1)
    raw: dict[str, Any] | None = None   # full provider response for debugging


class SearchResponse(BaseModel):
    """Container for a complete Tavily search call."""

    query: str
    results: list[SearchResult]
    fetched_at: datetime
