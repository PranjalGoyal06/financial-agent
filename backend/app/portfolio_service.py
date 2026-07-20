from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    HoldingModel,
    PortfolioImportModel,
    PortfolioModel,
    UserModel,
)
from app.portfolio_parser import CsvFieldError, parse_portfolio_csv


class PortfolioValidationError(Exception):
    def __init__(self, errors: list[CsvFieldError]) -> None:
        self.errors = errors
        super().__init__("Portfolio CSV failed validation.")

    def as_response(self) -> dict[str, Any]:
        return {
            "message": "Portfolio CSV failed validation.",
            "errors": [error.as_dict() for error in self.errors],
        }


async def replace_portfolio_from_csv(
    session: AsyncSession,
    *,
    user_id: str,
    csv_text: str,
    source_filename: str | None,
) -> dict[str, Any]:
    result = parse_portfolio_csv(csv_text)
    if result.errors:
        raise PortfolioValidationError(result.errors)

    async with session.begin():
        portfolio = await ensure_default_portfolio(session, user_id)
        portfolio_import = PortfolioImportModel(
            portfolio_id=portfolio.id,
            source_filename=source_filename,
            status="completed",
            imported_count=len(result.holdings),
            rejected_count=0,
        )
        session.add(portfolio_import)
        await session.flush()

        await session.execute(
            delete(HoldingModel).where(HoldingModel.portfolio_id == portfolio.id)
        )
        
        # Sort holdings chronologically for FIFO
        trades = sorted(
            result.holdings,
            key=lambda x: (x.trade_date or date.min, x.order_execution_time or datetime.min)
        )
        
        realized_pnl = Decimal("0.0")
        
        # canonical_ticker -> list of (quantity, price) lots
        lots_by_ticker = defaultdict(list)
        
        for trade in trades:
            lots = lots_by_ticker[trade.canonical_ticker]
            if trade.trade_type == "buy":
                lots.append({"qty": trade.quantity, "price": trade.price})
            elif trade.trade_type == "sell":
                sell_qty = trade.quantity
                while sell_qty > 0 and lots:
                    lot = lots[0]
                    if lot["qty"] <= sell_qty:
                        sell_qty -= lot["qty"]
                        realized_pnl += lot["qty"] * (trade.price - lot["price"])
                        lots.pop(0)
                    else:
                        lot["qty"] -= sell_qty
                        realized_pnl += sell_qty * (trade.price - lot["price"])
                        sell_qty = Decimal("0.0")
                        
        holding_models = []
        for trade in trades:
            if trade.canonical_ticker not in lots_by_ticker:
                continue
                
            lots = lots_by_ticker.pop(trade.canonical_ticker)
            if not lots:
                continue
                
            total_qty = sum(lot["qty"] for lot in lots)
            if total_qty <= 0:
                continue
                
            total_cost = sum(lot["qty"] * lot["price"] for lot in lots)
            avg_cost = total_cost / total_qty
            
            holding_models.append(
                HoldingModel(
                    portfolio_id=portfolio.id,
                    import_id=portfolio_import.id,
                    raw_ticker=trade.raw_ticker,
                    canonical_ticker=trade.canonical_ticker,
                    exchange=trade.exchange,
                    asset_class="equity",
                    quantity=total_qty,
                    avg_cost=avg_cost,
                    currency="INR",
                    purchase_date=trade.trade_date,
                )
            )

        session.add_all(holding_models)
        portfolio.realized_pnl = realized_pnl
        portfolio.updated_at = datetime.now(timezone.utc)

    return {
        "import_id": portfolio_import.id,
        "imported_count": len(result.holdings),
        "holdings": [_holding_response(holding) for holding in holding_models],
    }


async def get_portfolio(session: AsyncSession, *, user_id: str) -> dict[str, Any]:
    async with session.begin():
        portfolio = await ensure_default_portfolio(session, user_id)
        holdings_result = await session.execute(
            select(HoldingModel)
            .where(HoldingModel.portfolio_id == portfolio.id)
            .order_by(HoldingModel.created_at, HoldingModel.canonical_ticker)
        )
        holdings = list(holdings_result.scalars())

    return {
        "user_id": user_id,
        "portfolio_id": portfolio.id,
        "holdings": [_holding_response(holding) for holding in holdings],
        "total_holdings": len(holdings),
        "realized_pnl": _decimal_number(portfolio.realized_pnl),
        "updated_at": portfolio.updated_at.isoformat(),
    }


async def ensure_default_portfolio(
    session: AsyncSession,
    user_id: str,
) -> PortfolioModel:
    user = await session.get(UserModel, user_id)
    if user is None:
        user = UserModel(id=user_id)
        session.add(user)
        await session.flush()

    portfolio_result = await session.execute(
        select(PortfolioModel).where(PortfolioModel.user_id == user_id).limit(1)
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if portfolio is not None:
        return portfolio

    portfolio = PortfolioModel(user_id=user_id, name="Default Portfolio")
    session.add(portfolio)
    await session.flush()
    return portfolio


def _holding_response(holding: HoldingModel) -> dict[str, Any]:
    return {
        "id": holding.id,
        "raw_ticker": holding.raw_ticker,
        "canonical_ticker": holding.canonical_ticker,
        "exchange": holding.exchange,
        "asset_class": holding.asset_class,
        "quantity": _decimal_number(holding.quantity),
        "avg_cost": _decimal_number(holding.avg_cost),
        "currency": holding.currency,
        "purchase_date": holding.purchase_date.isoformat()
        if holding.purchase_date
        else None,
        "created_at": holding.created_at.isoformat(),
    }


def _decimal_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)
