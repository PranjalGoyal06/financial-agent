from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def compute_freshness(
    published_at: datetime | None,
    fetched_at: datetime,
) -> Literal["same_day", "this_week", "stale"]:
    """Determine freshness tier from the most recent of published_at / fetched_at.

    Uses published_at when available (news articles may have been fetched today
    but published a week ago — the article age is what matters for staleness).
    Falls back to fetched_at for market data and computed metrics that have no
    publication date concept.

    Tiers:
        same_day  — published/fetched today (UTC)
        this_week — within the last 7 days
        stale     — older than 7 days
    """
    reference = published_at or fetched_at
    now = datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    delta = now - reference
    if delta.days == 0:
        return "same_day"
    elif delta.days <= 7:
        return "this_week"
    return "stale"


class EvidenceItem(BaseModel):
    """A single piece of evidence in an EvidencePack.

    ``id`` is a short unique string (e.g. ``"news_001"``, ``"mkt_002"``)
    referenced directly in LLM citation outputs.  All evidence sources —
    Tavily results, yfinance data, Chroma-retrieved prior artifacts, and
    inline-computed metrics — are normalised into this schema before being
    included in a prompt.

    Layer classification:
        ``news``            → fetched from Tavily or yfinance .news
        ``market_data``     → quote / historical bars / fundamentals snapshot
        ``prior_artifact``  → retrieved from Chroma (prior research run)
        ``computed_metric`` → output of quant.lib / ta.lib (no I/O)
    """

    id: str
    type: Literal["news", "market_data", "prior_artifact", "computed_metric"]
    source: Literal["tavily", "yfinance", "chroma_retrieval", "internal_computation"]
    url: str | None = None           # news items only
    title: str | None = None         # news items only
    published_at: datetime | None = None  # article pub date — distinct from fetched_at
    fetched_at: datetime             # when this item was retrieved or computed
    freshness: Literal["same_day", "this_week", "stale"]
    summary: str                     # prompt-ready text; no raw HTML


class EvidencePack(BaseModel):
    """A collection of EvidenceItems for one research target.

    One EvidencePack is assembled per target before each synthesis node runs:
        - ``"macro"``         — market-wide context
        - sector name         — e.g. ``"Technology"``
        - canonical_ticker    — e.g. ``"RELIANCE.NS"``
        - ``"portfolio"``     — cross-ticker synthesis

    The same schema is reused across all node types to keep the citation-
    validation surface uniform.
    """

    pack_id: str
    target: str  # canonical_ticker / sector name / "macro" / "portfolio"
    items: list[EvidenceItem] = Field(default_factory=list)
    created_at: datetime

    # ── convenience helpers ────────────────────────────────────────────────────

    def get_item(self, item_id: str) -> EvidenceItem | None:
        """Return the item with the given id, or None if not present."""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    @property
    def item_ids(self) -> set[str]:
        """Set of all item IDs — used by validate_citations."""
        return {item.id for item in self.items}
