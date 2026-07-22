from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

HEADER_ALIASES = {
    "symbol": "symbol",
    "ticker": "symbol",
    "isin": "isin",
    "trade_date": "trade_date",
    "trade date": "trade_date",
    "exchange": "exchange",
    "trade_type": "trade_type",
    "trade type": "trade_type",
    "quantity": "quantity",
    "qty": "quantity",
    "qty.": "quantity",
    "price": "price",
    "order_execution_time": "order_execution_time",
    "order execution time": "order_execution_time",
}

SUFFIX_EXCHANGES = {
    ".NS": "NSE",
    ".BO": "BSE",
}


@dataclass(slots=True)
class CsvFieldError:
    row: int
    field: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "field": self.field,
            "message": self.message,
        }


@dataclass(slots=True)
class ParsedHolding:
    # We still call it ParsedHolding to minimize downstream renames if we want,
    # but functionally it's a TradebookRow.
    raw_ticker: str
    canonical_ticker: str
    isin: str
    trade_date: date | None
    exchange: str
    trade_type: str
    quantity: Decimal
    price: Decimal
    order_execution_time: datetime | None


@dataclass(slots=True)
class ParseResult:
    holdings: list[ParsedHolding]
    errors: list[CsvFieldError]


def parse_portfolio_csv(text: str) -> ParseResult:
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        return ParseResult(
            holdings=[],
            errors=[
                CsvFieldError(
                    row=1,
                    field="file",
                    message="CSV must include a header row.",
                )
            ],
        )

    normalized_headers = _normalized_headers(reader.fieldnames)
    source_headers = {_header_key(header) for header in reader.fieldnames}
    
    raw_rows = list(reader)
    if not raw_rows:
        return ParseResult(
            holdings=[],
            errors=[
                CsvFieldError(
                    row=1,
                    field="file",
                    message="CSV must include at least one row.",
                )
            ],
        )

    # First pass: map symbol to ISIN if present in any row
    symbol_isin_map: dict[str, str] = {}
    for raw_row in raw_rows:
        row = _canonical_row(raw_row, normalized_headers)
        symbol = _clean_optional(row.get("symbol"))
        isin = _clean_optional(row.get("isin"))
        if symbol and isin:
            symbol_isin_map[normalize_ticker(symbol)] = isin

    holdings: list[ParsedHolding] = []
    errors: list[CsvFieldError] = []

    for row_number, raw_row in enumerate(raw_rows, start=2):
        row = _canonical_row(raw_row, normalized_headers)
        row_errors = _validate_row(row, row_number)
        if row_errors:
            errors.extend(row_errors)
            continue

        raw_symbol = _clean_required(row["symbol"]).upper()
        canonical_ticker = normalize_ticker(raw_symbol)
        
        # trade_type normalization
        trade_type = _clean_required(row["trade_type"]).lower()
        if trade_type not in ("buy", "sell"):
            errors.append(
                CsvFieldError(
                    row=row_number,
                    field="trade_type",
                    message="Invalid trade_type. Must be buy or sell.",
                )
            )
            continue

        isin = _clean_optional(row.get("isin")) or symbol_isin_map.get(canonical_ticker, "") or symbol_isin_map.get(raw_symbol, "")

        holdings.append(
            ParsedHolding(
                raw_ticker=raw_symbol,
                canonical_ticker=canonical_ticker,
                isin=isin,
                trade_date=_parse_date(row.get("trade_date")),
                exchange=_normalize_exchange(
                    row.get("exchange"),
                    canonical_ticker,
                    source_headers,
                ),
                trade_type=trade_type,
                quantity=_parse_decimal(row["quantity"]),
                price=_parse_decimal(row["price"]),
                order_execution_time=_parse_datetime(row.get("order_execution_time")),
            )
        )

    return ParseResult(holdings=holdings, errors=errors)


TICKER_RENAMES: dict[str, str] = {
    "TATAMOTORS": "TMPV",
    "GOLD1": "GOLDBEES",
}


def normalize_ticker(value: str) -> str:
    cleaned = _clean_required(value).upper()
    return TICKER_RENAMES.get(cleaned, cleaned)


def _normalized_headers(fieldnames: list[str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for header in fieldnames:
        canonical = HEADER_ALIASES.get(_header_key(header))
        if canonical and canonical not in normalized:
            normalized[canonical] = header
    return normalized


def _canonical_row(
    raw_row: dict[str, str | None],
    normalized_headers: dict[str, str],
) -> dict[str, str]:
    row: dict[str, str] = {}
    for canonical, source_header in normalized_headers.items():
        row[canonical] = str(raw_row.get(source_header) or "").strip()
    return row


def _validate_row(row: dict[str, str], row_number: int) -> list[CsvFieldError]:
    errors: list[CsvFieldError] = []
    # Required fields for Tradebook
    for field in ("symbol", "trade_type", "quantity", "price"):
        if not _clean_optional(row.get(field)):
            errors.append(
                CsvFieldError(
                    row=row_number,
                    field=field,
                    message=f"{field} is required.",
                )
            )

    if _clean_optional(row.get("quantity")):
        try:
            quantity = _parse_decimal(row["quantity"])
        except ValueError as exc:
            errors.append(CsvFieldError(row_number, "quantity", str(exc)))
        else:
            if quantity <= 0:
                errors.append(
                    CsvFieldError(row_number, "quantity", "quantity must be positive.")
                )

    if _clean_optional(row.get("price")):
        try:
            price = _parse_decimal(row["price"])
        except ValueError as exc:
            errors.append(CsvFieldError(row_number, "price", str(exc)))
        else:
            if price < 0:
                errors.append(
                    CsvFieldError(
                        row_number,
                        "price",
                        "price must be non-negative.",
                    )
                )

    if _clean_optional(row.get("trade_date")):
        try:
            _parse_date(row.get("trade_date"))
        except ValueError as exc:
            errors.append(CsvFieldError(row_number, "trade_date", str(exc)))

    if _clean_optional(row.get("order_execution_time")):
        try:
            _parse_datetime(row.get("order_execution_time"))
        except ValueError as exc:
            errors.append(CsvFieldError(row_number, "order_execution_time", str(exc)))

    return errors


def _parse_decimal(value: str) -> Decimal:
    cleaned = _clean_required(value).replace(",", "")
    try:
        parsed = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError("must be numeric.") from exc
    if not parsed.is_finite():
        raise ValueError("must be numeric.")
    return parsed


def _parse_date(value: str | None) -> date | None:
    cleaned = _clean_optional(value)
    if not cleaned:
        return None
    try:
        return date.fromisoformat(cleaned[:10])
    except ValueError as exc:
        raise ValueError("trade_date must be ISO formatted (YYYY-MM-DD).") from exc


def _parse_datetime(value: str | None) -> datetime | None:
    cleaned = _clean_optional(value)
    if not cleaned:
        return None
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError("order_execution_time must be ISO formatted.") from exc


def _normalize_exchange(
    value: str | None,
    canonical_ticker: str,
    source_headers: set[str],
) -> str:
    explicit = _clean_optional(value)
    if explicit:
        return explicit.upper()
    for suffix, exchange in SUFFIX_EXCHANGES.items():
        if canonical_ticker.endswith(suffix):
            return exchange
    if "instrument" in source_headers and re.fullmatch(r"[A-Z0-9-]+", canonical_ticker):
        return "NSE"
    return "UNKNOWN"


def _header_key(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _clean_required(value: str | None) -> str:
    cleaned = _clean_optional(value)
    if not cleaned:
        raise ValueError("value is required.")
    return cleaned


def _clean_optional(value: str | None) -> str:
    return str(value or "").strip()

