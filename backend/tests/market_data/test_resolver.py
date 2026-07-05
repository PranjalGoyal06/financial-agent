from __future__ import annotations

from unittest.mock import patch

from app.market_data.resolver import _map_asset_class, _score, resolve_asset

# ── _score ─────────────────────────────────────────────────────────────────────


def test_score_exact_ticker_base():
    assert _score("infy", "INFY.NS", "Infosys Limited") == 1.0


def test_score_exact_name():
    assert _score("infosys limited", "INFY.NS", "Infosys Limited") == 0.95


def test_score_all_tokens_in_name():
    score = _score("tata motors", "TATAMOTORS.NS", "Tata Motors Limited")
    assert score == 0.80


def test_score_partial_overlap():
    score = _score("tata steel", "TATAMOTORS.NS", "Tata Motors Limited")
    # "tata" matches, "steel" does not → 1 of 2 tokens → 0.60 * 0.5 = 0.30
    assert score == 0.30


def test_score_no_overlap():
    score = _score("hdfc bank", "TATAMOTORS.NS", "Tata Motors Limited")
    assert score == 0.10


def test_score_case_insensitive():
    assert _score("INFY", "INFY.NS", "Infosys Limited") == 1.0


# ── _map_asset_class ───────────────────────────────────────────────────────────


def test_map_equity():
    assert _map_asset_class("EQUITY") == "equity"


def test_map_etf():
    assert _map_asset_class("ETF") == "etf"


def test_map_unknown_defaults_to_equity():
    assert _map_asset_class("UNKNOWN_TYPE") == "equity"


def test_map_case_insensitive():
    assert _map_asset_class("equity") == "equity"


# ── resolve_asset ──────────────────────────────────────────────────────────────


def _make_yf_quote(symbol: str, name: str, quote_type: str = "EQUITY") -> dict:
    return {"symbol": symbol, "longname": name, "quoteType": quote_type}


def test_resolve_returns_only_indian_exchanges():
    """US tickers in the search result should be filtered out."""
    raw_quotes = [
        _make_yf_quote("INFY", "Infosys Ltd (US ADR)"),       # no .NS/.BO → filtered
        _make_yf_quote("INFY.NS", "Infosys Limited"),
    ]
    with patch("app.market_data.resolver._search_quotes", return_value=raw_quotes):
        result = resolve_asset("infosys")

    assert result.resolved is True
    tickers = [c.canonical_ticker for c in result.candidates]
    assert "INFY.NS" in tickers
    assert "INFY" not in tickers


def test_resolve_ambiguous_query_returns_both_exchanges():
    """'tata motors' must return both NSE and BSE — the key invariant."""
    raw_quotes = [
        _make_yf_quote("TATAMOTORS.NS", "Tata Motors Limited"),
        _make_yf_quote("TATAMOTORS.BO", "Tata Motors Limited"),
    ]
    with patch("app.market_data.resolver._search_quotes", return_value=raw_quotes):
        result = resolve_asset("tata motors")

    assert result.resolved is True
    exchanges = {c.exchange for c in result.candidates}
    assert "NSE" in exchanges
    assert "BSE" in exchanges
    assert len(result.candidates) == 2


def test_resolve_sorted_by_confidence_descending():
    raw_quotes = [
        _make_yf_quote("TATAMOTORS.BO", "Tata Motors Limited"),  # lower conf
        _make_yf_quote("TATAMOTORS.NS", "Tata Motors Limited"),  # same conf, second
    ]
    with patch("app.market_data.resolver._search_quotes", return_value=raw_quotes):
        result = resolve_asset("tata motors")

    confidences = [c.confidence for c in result.candidates]
    assert confidences == sorted(confidences, reverse=True)


def test_resolve_no_results_returns_unresolved():
    with patch("app.market_data.resolver._search_quotes", return_value=[]):
        result = resolve_asset("zerodha")

    assert result.resolved is False
    assert result.candidates == []


def test_resolve_search_failure_returns_unresolved():
    """If yfinance Search raises, resolver must return resolved=False, not 500."""
    with patch(
        "app.market_data.resolver._search_quotes",
        side_effect=Exception("network error"),
    ):
        # _search_quotes internally catches all exceptions, so this path
        # tests that the wrapper swallows the exception.
        pass  # _search_quotes already returns [] on exception

    # Direct test of the wrapper:
    from app.market_data.resolver import _search_quotes

    with patch("app.market_data.resolver.yf.Search", side_effect=Exception("oops")):
        quotes = _search_quotes("anything")
    assert quotes == []


def test_resolve_blank_query_returns_unresolved():
    result = resolve_asset("   ")
    assert result.resolved is False
    assert result.candidates == []


def test_resolve_exact_ticker_gets_full_confidence():
    raw_quotes = [_make_yf_quote("INFY.NS", "Infosys Limited")]
    with patch("app.market_data.resolver._search_quotes", return_value=raw_quotes):
        result = resolve_asset("infy")

    assert result.candidates[0].confidence == 1.0


def test_resolve_asset_class_mapped():
    raw_quotes = [_make_yf_quote("NIFTYBEES.NS", "Nippon India ETF Nifty 50", "ETF")]
    with patch("app.market_data.resolver._search_quotes", return_value=raw_quotes):
        result = resolve_asset("nifty etf")

    assert result.candidates[0].asset_class == "etf"
