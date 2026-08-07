from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


ASSET_CLASSES = {"equity", "etf", "mf", "bond", "gold", "other"}


@dataclass(slots=True)
class PortfolioRow:
    ticker: str
    exchange: str
    asset_class: str
    quantity: float
    avg_buy_price: float
    currency: str
    purchase_date: date

    @classmethod
    def from_mapping(cls, row: dict[str, Any]) -> "PortfolioRow":
        missing = [field for field in ("ticker", "exchange", "asset_class", "quantity", "avg_buy_price", "currency", "purchase_date") if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

        asset_class = str(row["asset_class"]).strip().lower()
        if asset_class not in ASSET_CLASSES:
            raise ValueError(f"Invalid asset_class '{row['asset_class']}'.")

        try:
            quantity = float(row["quantity"])
        except ValueError as exc:
            raise ValueError("quantity must be numeric.") from exc
        if quantity <= 0:
            raise ValueError("quantity must be positive.")

        try:
            avg_buy_price = float(row["avg_buy_price"])
        except ValueError as exc:
            raise ValueError("avg_buy_price must be numeric.") from exc
        if avg_buy_price < 0:
            raise ValueError("avg_buy_price must be non-negative.")

        try:
            purchase_date = date.fromisoformat(str(row["purchase_date"]).strip())
        except ValueError as exc:
            raise ValueError("purchase_date must be ISO formatted (YYYY-MM-DD).") from exc

        return cls(
            ticker=str(row["ticker"]).strip(),
            exchange=str(row["exchange"]).strip(),
            asset_class=asset_class,
            quantity=quantity,
            avg_buy_price=avg_buy_price,
            currency=str(row["currency"]).strip().upper(),
            purchase_date=purchase_date,
        )

