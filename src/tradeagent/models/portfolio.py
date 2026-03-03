from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradeagent.models.base import Base


class Position(Base):
    __tablename__ = "position"
    __table_args__ = (
        Index(
            "ix_position_status_open",
            "stock_id",
            postgresql_where="status = 'OPEN'",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stock.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", server_default="OPEN", nullable=False)

    # Relationships
    stock: Mapped["Stock"] = relationship(lazy="selectin")  # noqa: F821


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshot"
    __table_args__ = (
        UniqueConstraint("date", name="uq_portfolio_snapshot_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    invested: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    daily_pnl: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    cumulative_pnl_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    num_positions: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    position_snapshots: Mapped[list[PositionSnapshot]] = relationship(
        back_populates="portfolio_snapshot", lazy="selectin"
    )


class PositionSnapshot(Base):
    __tablename__ = "position_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    portfolio_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio_snapshot.id"), nullable=False
    )
    stock_id: Mapped[int] = mapped_column(ForeignKey("stock.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    weight_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)

    # Relationships
    portfolio_snapshot: Mapped[PortfolioSnapshot] = relationship(back_populates="position_snapshots")
    stock: Mapped["Stock"] = relationship(lazy="selectin")  # noqa: F821
