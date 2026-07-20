from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.graph import get_agent
from app.main import _build_portfolio_context, _tool_output_summary

# ── _tool_output_summary ───────────────────────────────────────────────────────


def test_tool_output_summary_quote_formats_price() -> None:
    output = json.dumps(
        {"ticker": "INFY.NS", "price": 1523.5, "day_change_pct": 0.84}
    )
    result = _tool_output_summary("get_quote_tool", output)
    assert "INFY.NS" in result
    assert "1,523.50" in result
    assert "+0.84%" in result


def test_tool_output_summary_quote_negative_change() -> None:
    output = json.dumps(
        {"ticker": "TCS.NS", "price": 3400.0, "day_change_pct": -1.2}
    )
    result = _tool_output_summary("get_quote_tool", output)
    assert "-1.20%" in result


def test_tool_output_summary_resolve_shows_tickers() -> None:
    output = json.dumps(
        {
            "resolved": True,
            "candidates": [
                {"canonical_ticker": "TATAMOTORS.NS"},
                {"canonical_ticker": "TATAMOTORS.BO"},
            ],
        }
    )
    result = _tool_output_summary("resolve_asset_tool", output)
    assert "TATAMOTORS.NS" in result
    assert "Resolved" in result


def test_tool_output_summary_resolve_no_results() -> None:
    output = json.dumps({"resolved": False, "candidates": []})
    result = _tool_output_summary("resolve_asset_tool", output)
    assert "No matching ticker" in result


def test_tool_output_summary_historical_positive() -> None:
    output = json.dumps(
        {"ticker": "INFY.NS", "period": "6mo", "pct_change": 12.5}
    )
    result = _tool_output_summary("get_historical_data_tool", output)
    assert "+12.50%" in result


def test_tool_output_summary_historical_negative() -> None:
    output = json.dumps(
        {"ticker": "INFY.NS", "period": "1y", "pct_change": -5.3}
    )
    result = _tool_output_summary("get_historical_data_tool", output)
    assert "-5.30%" in result


def test_tool_output_summary_unknown_tool_truncates() -> None:
    output = "x" * 200
    result = _tool_output_summary("mystery_tool", output)
    assert len(result) <= 120


def test_tool_output_summary_handles_non_json() -> None:
    result = _tool_output_summary("get_quote_tool", "not-json")
    assert isinstance(result, str)


# ── _build_portfolio_context ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_portfolio_context_formats_holdings() -> None:
    mock_session = MagicMock()
    holdings = [
        {
            "canonical_ticker": "INFY.NS",
            "exchange": "NSE",
            "asset_class": "equity",
            "quantity": 100,
            "avg_cost": 1450.0,
            "currency": "INR",
        },
        {
            "canonical_ticker": "TCS.NS",
            "exchange": "NSE",
            "asset_class": "equity",
            "quantity": 50,
            "avg_cost": 3400.0,
            "currency": "INR",
        },
    ]

    with patch(
        "app.main.get_portfolio",
        new_callable=AsyncMock,
        return_value={"holdings": holdings},
    ):
        result = await _build_portfolio_context(mock_session)

    assert "INFY.NS" in result
    assert "TCS.NS" in result
    assert "| Ticker |" in result  # markdown table header


@pytest.mark.asyncio
async def test_build_portfolio_context_empty_returns_fallback() -> None:
    mock_session = MagicMock()

    with patch(
        "app.main.get_portfolio",
        new_callable=AsyncMock,
        return_value={"holdings": []},
    ):
        result = await _build_portfolio_context(mock_session)

    assert "No portfolio data" in result


@pytest.mark.asyncio
async def test_build_portfolio_context_on_db_error_returns_fallback() -> None:
    mock_session = MagicMock()

    with patch(
        "app.main.get_portfolio",
        new_callable=AsyncMock,
        side_effect=Exception("DB is down"),
    ):
        result = await _build_portfolio_context(mock_session)

    assert "No portfolio data" in result


# ── Agent Graph Compilation ────────────────────────────────────────────────────


def test_agent_graph_compiles_and_validates_structure() -> None:
    """Verify that get_agent successfully compiles the state graph and binds tools."""
    with patch("app.graph.get_chat_model") as mock_get_llm:
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        agent = get_agent("No portfolio data available", provider="groq", model="llama3")

        assert hasattr(agent, "stream")
        assert hasattr(agent, "astream_events")
        mock_get_llm.assert_called_once_with(
            temperature=0.1,
            streaming=True,
            provider="groq",
            model="llama3",
        )
