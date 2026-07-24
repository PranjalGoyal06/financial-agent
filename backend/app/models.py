from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
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
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), default=Decimal("0.0"), nullable=False
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


class MarketSnapshotModel(Base):
    """Cached market data payloads — quote and historical responses."""

    __tablename__ = "market_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticker: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    snapshot_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # "quote" | "historical"
    params_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )  # SHA-256 of (ticker, type, range, interval)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fresh_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class InstrumentModel(Base):
    """Instrument metadata — exchange, aliases, sector.

    Populated lazily from successful resolver calls; can be seeded manually.
    Serves as an override layer when the upstream search returns no results for
    a known alias.
    """

    __tablename__ = "instruments"

    ticker: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(120))
    industry: Mapped[str | None] = mapped_column(String(120))
    asset_class: Mapped[str] = mapped_column(String(40), nullable=False)
    aliases: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )  # JSON array of lowercase aliases, e.g. ["tata motors", "tatamotor"]
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class WatchlistItem(Base):
    """User watchlist entries.

    The ``get_watchlist()`` service reads from the ``holdings`` table by default
    (watchlist = current holdings) — this table is populated once a watchlist
    management UI exists.  Callers of ``get_watchlist()`` are insulated from
    this detail and will not need changes when the backing source switches.
    """

    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_ticker: Mapped[str] = mapped_column(String(40), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Artifact(Base):
    """Generalized Artifact model for the entire application.

    Stores reports, charts, and extracts generated by research runs,
    chat interactions, or manual user uploads.
    """

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # e.g., 'research', 'chat_create', 'user_upload', 'web_collected'
    
    source_ref_id: Mapped[str | None] = mapped_column(String(80), index=True)
    # Pointer to run_id, message_id, etc. depending on source_type
    
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # JSON array of strings
    
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # JSON dictionary for dynamic fields (e.g., target, recommendation, evidence_pack_json)
    
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    
    chroma_indexed: Mapped[bool] = mapped_column(default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class AuditEventModel(Base):
    """Audit events for tracking command executions and citations.
    
    Stores a JSON payload of the event data to allow flexibility across
    different command types and run modes.
    """

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    command: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    model_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    run_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
