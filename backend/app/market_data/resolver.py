from __future__ import annotations

import re

import yfinance as yf

from app.market_data.schemas import Asset, AssetResolution

# ── Exchange suffix → exchange label ──────────────────────────────────────────

_SUFFIX_EXCHANGE: dict[str, str] = {
    ".NS": "NSE",
    ".BO": "BSE",
}

# ── Asset class normalisation ──────────────────────────────────────────────────

_QUOTE_TYPE_MAP: dict[str, str] = {
    "EQUITY": "equity",
    "ETF": "etf",
    "MUTUALFUND": "mutual_fund",
    "BOND": "bond",
    "FUTURE": "futures",
    "OPTION": "options",
    "INDEX": "index",
}


def resolve_asset(query: str) -> AssetResolution:
    """Map a free-text query to NSE/BSE ticker candidates via yf.Search.

    Layer 1 (Raw fetch) — pure deterministic resolution, no LLM.

    Key invariant: ambiguous queries (same company listed on multiple exchanges)
    always produce multiple candidates with distinct exchange labels.
    'tata motors' → [TATAMOTORS.NS (NSE, conf=0.80), TATAMOTORS.BO (BSE, conf=0.80)]
    Neither is silently dropped or merged.

    Returns AssetResolution(resolved=False, candidates=[]) when:
    - yf.Search returns no results
    - All results are for non-Indian exchanges (no .NS/.BO suffix)
    - The query is blank after stripping
    """
    normalized = query.strip().lower()
    if not normalized:
        return AssetResolution(query=query, resolved=False, candidates=[])

    quotes: list[dict] = _search_quotes(normalized)
    candidates: list[Asset] = []

    for item in quotes:
        symbol: str = item.get("symbol", "")
        suffix = next(
            (s for s in _SUFFIX_EXCHANGE if symbol.upper().endswith(s)), None
        )
        if suffix is None:
            continue  # skip non-Indian results (US, LSE, etc.)

        exchange = _SUFFIX_EXCHANGE[suffix]
        name = item.get("longname") or item.get("shortname") or symbol
        asset_class = _map_asset_class(item.get("quoteType", ""))
        confidence = _score(normalized, symbol, name)

        candidates.append(
            Asset(
                canonical_ticker=symbol.upper(),
                exchange=exchange,  # type: ignore[arg-type]  # Literal enforced by suffix check
                name=name,
                asset_class=asset_class,
                currency="INR",
                confidence=confidence,
            )
        )

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return AssetResolution(
        query=query,
        resolved=len(candidates) > 0,
        candidates=candidates,
    )


# ── yfinance search wrapper ────────────────────────────────────────────────────


def _search_quotes(query: str) -> list[dict]:
    """Call yf.Search and return raw quote dicts. Returns [] on any failure."""
    try:
        results = yf.Search(query, max_results=20)
        quotes = getattr(results, "quotes", None)
        return quotes if isinstance(quotes, list) else []
    except Exception:
        return []


# ── Confidence scoring ─────────────────────────────────────────────────────────


def _score(query: str, symbol: str, name: str) -> float:
    """Heuristic confidence score in [0.0, 1.0].

    Tiers (descending):
      1.0   exact ticker base match  (query == "infy", symbol base == "INFY")
      0.95  exact full name match    (query == "infosys limited")
      0.80  all query tokens in name (query == "tata motors", name contains both)
      ≤0.60 partial token overlap    (proportional)
      0.10  fallback
    """
    query_lower = query.strip().lower()
    symbol_base = symbol.upper().split(".")[0].lower()
    name_lower = name.lower()

    if query_lower == symbol_base:
        return 1.0

    if query_lower == name_lower:
        return 0.95

    query_tokens = set(_tokenize(query_lower))
    name_tokens = set(_tokenize(name_lower))

    if not query_tokens:
        return 0.10

    if query_tokens <= name_tokens:
        return 0.80

    overlap = len(query_tokens & name_tokens)
    if overlap:
        return round(0.60 * overlap / len(query_tokens), 2)

    return 0.10


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[\s\-&]+", text) if t]


def _map_asset_class(quote_type: str) -> str:
    return _QUOTE_TYPE_MAP.get(quote_type.upper(), "equity")
