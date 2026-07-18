from __future__ import annotations

from app.portfolio_parser import parse_portfolio_csv


def test_valid_canonical_csv_imports_holdings() -> None:
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
    assert float(holding.quantity) == 3
    assert float(holding.price) == 1420.5
    assert holding.trade_date.isoformat() == "2024-01-15"


def test_valid_broker_style_csv_imports_holdings() -> None:
    result = parse_portfolio_csv(
        '"symbol","isin","trade_type","qty","price"\n'
        '"HDFCBANK","INE040A01034","sell",3,800.15\n'
    )

    assert result.errors == []
    holding = result.holdings[0]
    assert holding.canonical_ticker == "HDFCBANK"
    assert holding.isin == "INE040A01034"
    assert holding.trade_type == "sell"
    assert float(holding.quantity) == 3
    assert float(holding.price) == 800.15


def test_missing_required_fields_report_row_numbers() -> None:
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
