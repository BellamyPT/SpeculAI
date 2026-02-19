from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradeagent.models.base import Base


class Benchmark(Base):
    __tablename__ = "benchmark"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    prices: Mapped[list[BenchmarkPrice]] = relationship(back_populates="benchmark", lazy="selectin")


class BenchmarkPrice(Base):
    __tablename__ = "benchmark_price"
    __table_args__ = (
        UniqueConstraint("benchmark_id", "date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    benchmark_id: Mapped[int] = mapped_column(ForeignKey("benchmark.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    # Relationships
    benchmark: Mapped[Benchmark] = relationship(back_populates="prices")
