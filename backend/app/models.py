from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class PortfolioModel(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class PortfolioImportModel(Base):
    __tablename__ = "portfolio_imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_filename: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    imported_count: Mapped[int] = mapped_column(nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class HoldingModel(Base):
    __tablename__ = "holdings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    import_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_ticker: Mapped[str] = mapped_column(String(40), nullable=False)
    canonical_ticker: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True
    )
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
