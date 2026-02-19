from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradeagent.models.base import Base, TimestampMixin


class DecisionReport(TimestampMixin, Base):
    __tablename__ = "decision_report"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="confidence_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stock.id"), nullable=False)
    pipeline_run_id: Mapped[UUID] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    technical_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    news_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    memory_references: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    portfolio_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    outcome_pnl: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    outcome_benchmark_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    outcome_assessed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_backtest: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    backtest_run_id: Mapped[UUID | None] = mapped_column(nullable=True)

    # Relationships
    stock: Mapped["Stock"] = relationship(lazy="selectin")  # noqa: F821
    context_items: Mapped[list[DecisionContextItem]] = relationship(
        back_populates="decision_report", lazy="selectin"
    )


class DecisionContextItem(TimestampMixin, Base):
    __tablename__ = "decision_context_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_report_id: Mapped[int] = mapped_column(
        ForeignKey("decision_report.id"), nullable=False
    )
    context_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)

    # Relationships
    decision_report: Mapped[DecisionReport] = relationship(back_populates="context_items")
