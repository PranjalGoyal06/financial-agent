from __future__ import annotations

import csv
from dataclasses import asdict
from io import StringIO
from typing import Any, TextIO
from uuid import uuid4

from app.db.repositories.holdings_repository import (
    DEFAULT_HOLDINGS_REPOSITORY,
    HoldingRecord,
    HoldingsRepository,
)
from app.integrations import yfinance_client
from app.schemas.domain import PortfolioRow
from app.services.market_data_service import (
    DEFAULT_MARKET_DATA_SERVICE,
    MarketDataService,
)


class PortfolioService:
    def __init__(
        self,
        repository: HoldingsRepository | None = None,
        market_data_service: MarketDataService | None = None,
        user_id: str = "demo-user",
    ) -> None:
        self.repository = repository or DEFAULT_HOLDINGS_REPOSITORY
        self.market_data_service = market_data_service or DEFAULT_MARKET_DATA_SERVICE
        self.user_id = user_id

    def ingest_csv(
        self,
        csv_input: str | TextIO,
        source_filename: str | None = None,
    ) -> dict[str, Any]:
        text = csv_input.read() if hasattr(csv_input, "read") else str(csv_input)
        reader = csv.DictReader(StringIO(text))
        import_id = str(uuid4())
        imported_rows: list[tuple[dict[str, Any], HoldingRecord]] = []
        rejected: list[dict[str, Any]] = []

        for raw_row in reader:
            try:
                row = PortfolioRow.from_mapping(raw_row)
            except ValueError as exc:
                rejected.append({"row": raw_row, "reason": str(exc)})
                continue

            resolution = yfinance_client.resolve_ticker(row.ticker, row.exchange)
            if not resolution.ok or not resolution.resolved_ticker:
                rejected.append(
                    {
                        "row": raw_row,
                        "reason": (
                            resolution.error.message
                            if resolution.error
                            else "Ticker could not be resolved."
                        ),
                    }
                )
                continue

            imported_rows.append(
                (
                    raw_row,
                    HoldingRecord(
                        user_id=self.user_id,
                        raw_ticker=row.ticker,
                        canonical_ticker=resolution.resolved_ticker,
                        exchange=row.exchange.upper(),
                        asset_class=row.asset_class,
                        quantity=row.quantity,
                        avg_buy_price=row.avg_buy_price,
                        currency=row.currency,
                        purchase_date=row.purchase_date.isoformat(),
                        portfolio_import_id=import_id,
                    ),
                )
            )

        if not imported_rows:
            return {
                "import_id": import_id,
                "source_filename": source_filename,
                "imported": 0,
                "rejected": rejected,
                "holdings": [],
            }

        holdings = [holding for _, holding in imported_rows]
        try:
            self.repository.replace_for_user(self.user_id, holdings)
        except Exception as exc:  # noqa: BLE001
            for raw_row, _holding in imported_rows:
                rejected.append(
                    {"row": raw_row, "reason": f"database_write_failed: {exc}"}
                )
            return {
                "import_id": import_id,
                "source_filename": source_filename,
                "imported": 0,
                "rejected": rejected,
                "holdings": [],
            }

        return {
            "import_id": import_id,
            "source_filename": source_filename,
            "imported": len(holdings),
            "rejected": rejected,
            "holdings": [asdict(holding) for holding in holdings],
        }

    def portfolio_valuation(self) -> dict[str, Any]:
        holdings = self.repository.list_by_user(self.user_id)
        invested_amount = sum(
            holding.quantity * holding.avg_buy_price for holding in holdings
        )
        if not holdings:
            return {
                "invested_amount": 0,
                "current_value": None,
                "unrealized_pnl": None,
                "today_pnl": None,
                "priced_holdings": 0,
                "unpriced_holdings": 0,
                "is_stale": False,
                "currency": "INR",
                "quotes": [],
            }

        exchanges = {
            holding.canonical_ticker: holding.exchange for holding in holdings
        }
        quote_results = self.market_data_service.get_quotes(
            [holding.canonical_ticker for holding in holdings],
            exchanges,
        )

        quotes: list[dict[str, Any]] = []
        current_value = 0.0
        today_pnl = 0.0
        priced_holdings = 0
        has_day_change = False
        is_stale = False

        for holding in holdings:
            envelope = quote_results.get(holding.canonical_ticker)
            quote = envelope.value if envelope else None
            price = _numeric_quote_value(quote, "price")
            change = _numeric_quote_value(quote, "change")
            position_value = price * holding.quantity if price is not None else None
            position_day_pnl = (
                change * holding.quantity if change is not None else None
            )

            if position_value is not None:
                current_value += position_value
                priced_holdings += 1
            if position_day_pnl is not None:
                today_pnl += position_day_pnl
                has_day_change = True
            if envelope and envelope.is_stale:
                is_stale = True

            quotes.append(
                {
                    "holding_id": holding.holding_id,
                    "ticker": holding.raw_ticker,
                    "canonical_ticker": holding.canonical_ticker,
                    "price": price,
                    "change": change,
                    "change_percent": _numeric_quote_value(quote, "change_percent"),
                    "position_value": position_value,
                    "position_day_pnl": position_day_pnl,
                    "currency": (quote or {}).get("currency") or holding.currency,
                    "source": envelope.source if envelope else "yfinance",
                    "is_stale": envelope.is_stale if envelope else True,
                    "error": (
                        envelope.error.message
                        if envelope and envelope.error is not None
                        else None
                    ),
                }
            )

        has_full_valuation = priced_holdings == len(holdings)
        return {
            "invested_amount": invested_amount,
            "current_value": current_value if has_full_valuation else None,
            "unrealized_pnl": (
                current_value - invested_amount if has_full_valuation else None
            ),
            "today_pnl": today_pnl if has_day_change else None,
            "priced_holdings": priced_holdings,
            "unpriced_holdings": len(holdings) - priced_holdings,
            "is_stale": is_stale,
            "currency": holdings[0].currency if holdings else "INR",
            "quotes": quotes,
        }


def _numeric_quote_value(
    quote: dict[str, Any] | None,
    key: str,
) -> float | None:
    if not quote:
        return None
    value = quote.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


DEFAULT_PORTFOLIO_SERVICE = PortfolioService()
