from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

HEADER_ALIASES = {
    "ticker": "ticker",
    "instrument": "ticker",
    "exchange": "exchange",
    "asset_class": "asset_class",
    "asset class": "asset_class",
    "quantity": "quantity",
    "qty.": "quantity",
    "qty": "quantity",
    "avg_cost": "avg_cost",
    "avg cost": "avg_cost",
    "avg. cost": "avg_cost",
    "avg_buy_price": "avg_cost",
    "avg buy price": "avg_cost",
    "currency": "currency",
    "purchase_date": "purchase_date",
    "purchase date": "purchase_date",
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
    raw_ticker: str
    canonical_ticker: str
    exchange: str
    asset_class: str
    quantity: Decimal
    avg_cost: Decimal
    currency: str
    purchase_date: date | None


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
    holdings: list[ParsedHolding] = []
    errors: list[CsvFieldError] = []

    for row_number, raw_row in enumerate(reader, start=2):
        row = _canonical_row(raw_row, normalized_headers)
        row_errors = _validate_row(row, row_number)
        if row_errors:
            errors.extend(row_errors)
            continue

        ticker = _clean_required(row["ticker"])
        canonical_ticker = normalize_ticker(ticker)
        holdings.append(
            ParsedHolding(
                raw_ticker=canonical_ticker,
                canonical_ticker=canonical_ticker,
                exchange=_normalize_exchange(
                    row.get("exchange"),
                    canonical_ticker,
                    source_headers,
                ),
                asset_class=_normalize_asset_class(row.get("asset_class")),
                quantity=_parse_decimal(row["quantity"]),
                avg_cost=_parse_decimal(row["avg_cost"]),
                currency=_normalize_currency(row.get("currency")),
                purchase_date=_parse_date(row.get("purchase_date")),
            )
        )

    if not holdings and not errors:
        errors.append(
            CsvFieldError(
                row=1,
                field="file",
                message="CSV must include at least one row.",
            )
        )

    return ParseResult(holdings=holdings, errors=errors)


def normalize_ticker(value: str) -> str:
    return _clean_required(value).upper()


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
    for field in ("ticker", "quantity", "avg_cost"):
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

    if _clean_optional(row.get("avg_cost")):
        try:
            avg_cost = _parse_decimal(row["avg_cost"])
        except ValueError as exc:
            errors.append(CsvFieldError(row_number, "avg_cost", str(exc)))
        else:
            if avg_cost < 0:
                errors.append(
                    CsvFieldError(
                        row_number,
                        "avg_cost",
                        "avg_cost must be non-negative.",
                    )
                )

    if _clean_optional(row.get("purchase_date")):
        try:
            _parse_date(row.get("purchase_date"))
        except ValueError as exc:
            errors.append(CsvFieldError(row_number, "purchase_date", str(exc)))

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
        return date.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError("purchase_date must be ISO formatted (YYYY-MM-DD).") from exc


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


def _normalize_asset_class(value: str | None) -> str:
    cleaned = _clean_optional(value)
    return cleaned.lower() if cleaned else "equity"


def _normalize_currency(value: str | None) -> str:
    cleaned = _clean_optional(value)
    return cleaned.upper() if cleaned else "INR"


def _header_key(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _clean_required(value: str | None) -> str:
    cleaned = _clean_optional(value)
    if not cleaned:
        raise ValueError("value is required.")
    return cleaned


def _clean_optional(value: str | None) -> str:
    return str(value or "").strip()
