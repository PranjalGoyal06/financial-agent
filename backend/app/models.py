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


class ResearchArtifact(Base):
    """Artifacts produced by the deep research graph.

    One row per node output (macro / sector / ticker / portfolio) per run.
    All artifacts from a single graph execution share the same ``run_id``.

    ``recommendation`` and ``confidence_score`` are denormalized from the
    structured LLM output at persist time so the portfolio tab can render
    recommendation pills with a single SQL query — no JSON parsing needed.
    Only ticker-type rows carry these values; other types leave them NULL.
    """

    __tablename__ = "research_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # "macro" | "sector" | "ticker" | "portfolio"
    target: Mapped[str | None] = mapped_column(String(40))
    # canonical_ticker / sector name / null for macro & portfolio
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_pack_json: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(String(20))
    # "buy"|"add"|"hold"|"reduce"|"watch"|"no_action"|"insufficient_data"
    confidence_score: Mapped[int | None] = mapped_column(Integer)
    # 0-100 — drives the confidence label on the portfolio tab recommendation pill
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
