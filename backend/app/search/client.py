from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from tavily import TavilyClient

from app.config import settings
from app.db import AsyncSessionLocal
from app.evidence.schemas import EvidenceItem, compute_freshness
from app.market_data.cache import get_cached, make_params_hash, put_cache
from app.search.schemas import SearchResult

_SNAPSHOT_TYPE = "search_snapshot"
_CACHE_TTL_MINUTES = 20
_PROVIDER = "tavily"

logger = logging.getLogger(__name__)


# ── ID generation ──────────────────────────────────────────────────────────────


def _item_id(url: str) -> str:
    """Stable 8-hex-char ID for a search result, derived from URL.

    Using a URL hash (rather than a sequential counter) means the same article
    will always get the same ID across different search calls, which prevents
    duplicate EvidenceItems when the same article appears in both a sector
    query and a company-specific query.
    """
    return "news_" + hashlib.sha256(url.encode()).hexdigest()[:8]


# ── Date parsing ───────────────────────────────────────────────────────────────


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse Tavily's published_date string to a UTC-aware datetime.

    Tavily may return ``"2024-01-15T10:30:00"``, ``"2024-01-15"``, or None.
    Returns None on any parse failure rather than raising.
    """
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    logger.debug("Could not parse Tavily date string: %r", date_str)
    return None


# ── Result mapping ─────────────────────────────────────────────────────────────


def _to_search_result(raw: dict[str, Any]) -> SearchResult:
    return SearchResult(
        title=raw.get("title", ""),
        url=raw.get("url", ""),
        content=raw.get("content", ""),
        published_date=raw.get("published_date"),
        score=float(raw.get("score", 0.0)),
        raw=raw,
    )


def _to_evidence_item(result: SearchResult) -> EvidenceItem:
    """Normalise a SearchResult into the canonical EvidenceItem schema."""
    fetched_at = datetime.now(timezone.utc)
    published_at = _parse_date(result.published_date)
    return EvidenceItem(
        id=_item_id(result.url),
        type="news",
        source="tavily",
        url=result.url,
        title=result.title or None,
        published_at=published_at,
        fetched_at=fetched_at,
        freshness=compute_freshness(published_at, fetched_at),
        summary=result.content.strip() or result.title or "",
    )


# ── Cache helpers ──────────────────────────────────────────────────────────────


def _items_to_payload(items: list[EvidenceItem]) -> dict:
    """Serialise items to the dict shape stored in market_snapshots.payload_json."""
    return {"items": [item.model_dump(mode="json") for item in items]}


def _payload_to_items(payload: dict) -> list[EvidenceItem]:
    return [EvidenceItem.model_validate(d) for d in payload.get("items", [])]


async def _read_cache(params_hash: str) -> list[EvidenceItem] | None:
    async with AsyncSessionLocal() as session:
        cached = await get_cached(session, _SNAPSHOT_TYPE, params_hash)
    if cached is None:
        return None
    return _payload_to_items(cached)


async def _write_cache(
    params_hash: str, items: list[EvidenceItem], fresh_until: datetime
) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await put_cache(
                session,
                snapshot_type=_SNAPSHOT_TYPE,
                params_hash=params_hash,
                # 'ticker' is a required column in market_snapshots; for search
                # snapshots there is no ticker — we use the sentinel "search".
                # The params_hash is the true unique key.
                ticker="search",
                payload=_items_to_payload(items),
                provider=_PROVIDER,
                fresh_until=fresh_until,
            )


# ── Public API ─────────────────────────────────────────────────────────────────


async def search(query: str, max_results: int = 5) -> list[EvidenceItem]:
    """Search via Tavily and return results normalised to EvidenceItem.

    Cache-aware: results are stored in ``market_snapshots``
    (``snapshot_type="search_snapshot"``) for ``_CACHE_TTL_MINUTES`` minutes.
    A cache hit costs one lightweight DB read with no Tavily API call.

    Returns an empty list (never raises) if Tavily is unavailable or the
    API key is not configured — callers treat empty news evidence as low-
    confidence, not as a hard error.

    Args:
        query:       Free-text search string.  Callers are responsible for
                     constructing a well-scoped query (company + "stock news",
                     macro outlook, sector + "India" etc.).
        max_results: Maximum number of results to return (1–10).
                     Lower values cost fewer Tavily credits.
    """
    params_hash = make_params_hash(
        "search", _SNAPSHOT_TYPE, query=query, max_results=str(max_results)
    )

    # ── Cache read ─────────────────────────────────────────────────────────────
    cached_items = await _read_cache(params_hash)
    if cached_items is not None:
        logger.debug("search cache hit (n=%d): %r", len(cached_items), query)
        return cached_items

    # ── Live Tavily call ───────────────────────────────────────────────────────
    if not settings.tavily_api_key:
        logger.warning("TAVILY_API_KEY not set — search returning empty results")
        return []

    logger.info("Tavily search (max=%d): %r", max_results, query)
    try:
        response_raw: dict = await asyncio.to_thread(
            _call_tavily, query, max_results
        )
    except Exception as exc:
        logger.error("Tavily search failed for query %r: %s", query, exc)
        return []

    results = [_to_search_result(r) for r in response_raw.get("results", [])]
    items = [_to_evidence_item(r) for r in results]

    # ── Cache write ────────────────────────────────────────────────────────────
    if items:
        fresh_until = datetime.now(timezone.utc) + timedelta(minutes=_CACHE_TTL_MINUTES)
        try:
            await _write_cache(params_hash, items, fresh_until)
        except Exception as exc:
            # Cache write failure is non-fatal — caller still gets fresh results.
            logger.warning("search cache write failed: %s", exc)

    return items


def _call_tavily(query: str, max_results: int) -> dict:
    """Synchronous Tavily call — wrapped with asyncio.to_thread by the caller."""
    client = TavilyClient(api_key=settings.tavily_api_key)
    return client.search(query, max_results=max_results, search_depth="basic")
