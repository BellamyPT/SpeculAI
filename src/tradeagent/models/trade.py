from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradeagent.models.base import Base, TimestampMixin


class Trade(TimestampMixin, Base):
    __tablename__ = "trade"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stock.id"), nullable=False)
    decision_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_report.id"), nullable=True
    )
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_backtest: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    backtest_run_id: Mapped[UUID | None] = mapped_column(nullable=True)

    # Relationships
    stock: Mapped["Stock"] = relationship(lazy="selectin")  # noqa: F821
    decision_report: Mapped["DecisionReport | None"] = relationship(lazy="selectin")  # noqa: F821
