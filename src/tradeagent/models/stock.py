from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradeagent.models.base import Base, TimestampMixin, UpdatedAtMixin


class Stock(TimestampMixin, UpdatedAtMixin, Base):
    __tablename__ = "stock"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    # Relationships
    prices: Mapped[list[StockPrice]] = relationship(back_populates="stock", lazy="selectin")
    fundamentals: Mapped[list[StockFundamental]] = relationship(back_populates="stock", lazy="selectin")


class StockPrice(Base):
    __tablename__ = "stock_price"
    __table_args__ = (
        UniqueConstraint("stock_id", "date"),
        Index("ix_stock_price_stock_id_date_desc", "stock_id", "date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stock.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    adj_close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationships
    stock: Mapped[Stock] = relationship(back_populates="prices")


class StockFundamental(Base):
    __tablename__ = "stock_fundamental"
    __table_args__ = (
        UniqueConstraint("stock_id", "snapshot_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stock.id"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    forward_pe: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    peg_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    price_to_book: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    price_to_sales: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    eps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    revenue_growth: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    earnings_growth: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    profit_margin: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    debt_to_equity: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    current_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    beta: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    next_earnings_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Relationships
    stock: Mapped[Stock] = relationship(back_populates="fundamentals")
