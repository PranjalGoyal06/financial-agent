from __future__ import annotations

from app.market_data.cache import make_params_hash

# ── make_params_hash ───────────────────────────────────────────────────────────


def test_hash_is_deterministic():
    h1 = make_params_hash("INFY.NS", "quote")
    h2 = make_params_hash("INFY.NS", "quote")
    assert h1 == h2


def test_hash_differs_by_ticker():
    h1 = make_params_hash("INFY.NS", "quote")
    h2 = make_params_hash("TCS.NS", "quote")
    assert h1 != h2


def test_hash_differs_by_snapshot_type():
    h1 = make_params_hash("INFY.NS", "quote")
    h2 = make_params_hash("INFY.NS", "historical")
    assert h1 != h2


def test_hash_differs_by_range():
    h1 = make_params_hash("INFY.NS", "historical", range="6mo", interval="1d")
    h2 = make_params_hash("INFY.NS", "historical", range="1y", interval="1d")
    assert h1 != h2


def test_hash_differs_by_interval():
    h1 = make_params_hash("INFY.NS", "historical", range="6mo", interval="1d")
    h2 = make_params_hash("INFY.NS", "historical", range="6mo", interval="1wk")
    assert h1 != h2


def test_hash_kwarg_order_independent():
    """Kwargs should be sorted so key order never changes the hash."""
    h1 = make_params_hash("INFY.NS", "historical", range="6mo", interval="1d")
    h2 = make_params_hash("INFY.NS", "historical", interval="1d", range="6mo")
    assert h1 == h2


def test_hash_is_64_hex_chars():
    h = make_params_hash("INFY.NS", "quote")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
