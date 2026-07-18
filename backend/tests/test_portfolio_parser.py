from __future__ import annotations

from decimal import Decimal
from app.portfolio_parser import parse_portfolio_csv, normalize_ticker


def test_valid_canonical_csv_imports_holdings() -> None:
    """Verify that a standard CSV with canonical headers parses correctly."""
    result = parse_portfolio_csv(
        "symbol,isin,exchange,trade_type,quantity,price,trade_date\n"
        "INFY.NS,INE009A01021,NSE,buy,3,1420.5,2024-01-15\n"
    )

    assert result.errors == []
    assert len(result.holdings) == 1
    holding = result.holdings[0]
    assert holding.raw_ticker == "INFY.NS"
    assert holding.canonical_ticker == "INFY.NS"
    assert holding.isin == "INE009A01021"
    assert holding.exchange == "NSE"
    assert holding.trade_type == "buy"
    assert holding.quantity == Decimal("3")
    assert holding.price == Decimal("1420.5")
    assert holding.trade_date is not None
    assert holding.trade_date.isoformat() == "2024-01-15"


def test_valid_broker_style_csv_imports_holdings() -> None:
    """Verify that broker-style CSVs with header aliases (e.g., 'qty') parse correctly."""
    result = parse_portfolio_csv(
        '"symbol","isin","trade_type","qty","price"\n'
        '"HDFCBANK","INE040A01034","sell",3,800.15\n'
    )

    assert result.errors == []
    assert len(result.holdings) == 1
    holding = result.holdings[0]
    assert holding.canonical_ticker == "HDFCBANK"
    assert holding.isin == "INE040A01034"
    assert holding.trade_type == "sell"
    assert holding.quantity == Decimal("3")
    assert holding.price == Decimal("800.15")


def test_missing_required_fields_report_row_numbers() -> None:
    """Verify that omitting required fields produces explicit errors with accurate row numbers."""
    result = parse_portfolio_csv("symbol,quantity\nAAPL,1\n")

    assert result.holdings == []
    assert [error.as_dict() for error in result.errors] == [
        {
            "row": 2,
            "field": "isin",
            "message": "isin is required.",
        },
        {
            "row": 2,
            "field": "trade_type",
            "message": "trade_type is required.",
        },
        {
            "row": 2,
            "field": "price",
            "message": "price is required.",
        }
    ]


def test_invalid_numeric_fields_report_field_errors() -> None:
    """Verify that non-positive quantities or non-numeric prices generate validation errors."""
    result = parse_portfolio_csv(
        "symbol,isin,trade_type,quantity,price\n"
        "INFY,INE009A01021,buy,0,100\n"
        "TCS,INE467B01029,buy,2,not-a-number\n"
    )

    assert result.holdings == []
    assert [error.as_dict() for error in result.errors] == [
        {
            "row": 2,
            "field": "quantity",
            "message": "quantity must be positive.",
        },
        {
            "row": 3,
            "field": "price",
            "message": "must be numeric.",
        },
    ]


def test_invalid_date_formats_report_field_errors() -> None:
    """Verify that invalid date or datetime formats generate validation errors."""
    result = parse_portfolio_csv(
        "symbol,isin,trade_type,quantity,price,trade_date,order_execution_time\n"
        "INFY,INE009A01021,buy,10,100,2024/01/15,invalid-time\n"
    )

    assert result.holdings == []
    assert [error.as_dict() for error in result.errors] == [
        {
            "row": 2,
            "field": "trade_date",
            "message": "trade_date must be ISO formatted (YYYY-MM-DD).",
        },
        {
            "row": 2,
            "field": "order_execution_time",
            "message": "order_execution_time must be ISO formatted.",
        },
    ]


def test_empty_or_no_header_csv_fails() -> None:
    """Verify that empty files or files missing header rows return structural errors."""
    result_empty = parse_portfolio_csv("")
    assert len(result_empty.errors) == 1
    assert "header row" in result_empty.errors[0].message

    result_no_data = parse_portfolio_csv("symbol,isin,trade_type,quantity,price\n")
    assert len(result_no_data.errors) == 1
    assert "at least one row" in result_no_data.errors[0].message


def test_normalize_ticker_uppercases_and_strips() -> None:
    """Verify normalize_ticker uppercases and strips whitespace."""
    assert normalize_ticker(" infy.ns ") == "INFY.NS"
    assert normalize_ticker("TCS.bo") == "TCS.BO"
