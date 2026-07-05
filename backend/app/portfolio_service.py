from __future__ import annotations

from datetime import datetime, timezone
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
from app.portfolio_parser import CsvFieldError, ParsedHolding, parse_portfolio_csv


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
        holding_models = [
            _holding_model(portfolio.id, portfolio_import.id, holding)
            for holding in result.holdings
        ]
        session.add_all(holding_models)
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


def _holding_model(
    portfolio_id: str,
    import_id: str,
    holding: ParsedHolding,
) -> HoldingModel:
    return HoldingModel(
        portfolio_id=portfolio_id,
        import_id=import_id,
        raw_ticker=holding.raw_ticker,
        canonical_ticker=holding.canonical_ticker,
        exchange=holding.exchange,
        asset_class=holding.asset_class,
        quantity=holding.quantity,
        avg_cost=holding.avg_cost,
        currency=holding.currency,
        purchase_date=holding.purchase_date,
    )


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
