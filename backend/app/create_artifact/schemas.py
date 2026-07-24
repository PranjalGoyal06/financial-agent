from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class ArtifactIntent(BaseModel):
    needs_fresh_grounding: bool = Field(description="True if the request requires fetching new market data or news. False if it just summarizes the existing chat history.")
    title: str = Field(description="A short descriptive title for the artifact.")
    filename: str = Field(description="A suitable filename ending in .md")
    search_queries: list[str] = Field(default_factory=list, description="If needs_fresh_grounding is True, list up to 3 search queries to gather context.")


class ArtifactCard(BaseModel):
    filename: str
    title: str
    content_preview: str
    full_content_ref: str
    created_at: str
    evidence_ids: list[str] | None = None
    source_context: Literal["conversation_summary", "fresh_analysis"]
