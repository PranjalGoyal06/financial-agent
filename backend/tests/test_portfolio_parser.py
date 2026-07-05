from __future__ import annotations

from app.portfolio_parser import parse_portfolio_csv


def test_valid_canonical_csv_imports_holdings() -> None:
    result = parse_portfolio_csv(
        "ticker,exchange,asset_class,quantity,avg_buy_price,currency,purchase_date\n"
        "infy.ns,NSE,equity,3,1420.5,INR,2024-01-15\n"
    )

    assert result.errors == []
    assert len(result.holdings) == 1
    holding = result.holdings[0]
    assert holding.raw_ticker == "INFY.NS"
    assert holding.canonical_ticker == "INFY.NS"
    assert holding.exchange == "NSE"
    assert holding.asset_class == "equity"
    assert float(holding.quantity) == 3
    assert float(holding.avg_cost) == 1420.5
    assert holding.currency == "INR"
    assert holding.purchase_date.isoformat() == "2024-01-15"


def test_valid_broker_style_csv_imports_holdings() -> None:
    result = parse_portfolio_csv(
        '"Instrument","Qty.","Avg. cost","LTP"\n'
        '"HDFCBANK",3,800,796.15\n'
    )

    assert result.errors == []
    holding = result.holdings[0]
    assert holding.canonical_ticker == "HDFCBANK"
    assert holding.exchange == "NSE"
    assert holding.asset_class == "equity"
    assert holding.currency == "INR"
    assert float(holding.avg_cost) == 800


def test_missing_required_fields_report_row_numbers() -> None:
    result = parse_portfolio_csv("Ticker,Quantity,Sector\nAAPL,1,IT\n")

    assert result.holdings == []
    assert [error.as_dict() for error in result.errors] == [
        {
            "row": 2,
            "field": "avg_cost",
            "message": "avg_cost is required.",
        }
    ]


def test_invalid_numeric_fields_report_field_errors() -> None:
    result = parse_portfolio_csv(
        "ticker,quantity,avg_cost\n"
        "INFY,0,100\n"
        "TCS,2,not-a-number\n"
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
            "field": "avg_cost",
            "message": "must be numeric.",
        },
    ]
