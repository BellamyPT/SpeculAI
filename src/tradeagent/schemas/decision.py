from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class DecisionContextItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    decision_report_id: int
    context_type: str
    source: str
    content: str
    relevance_score: Decimal | None
    created_at: datetime


class DecisionReportResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    stock_id: int
    ticker: str | None = None
    pipeline_run_id: UUID
    action: str
    confidence: Decimal
    reasoning: str
    is_backtest: bool
    backtest_run_id: UUID | None
    created_at: datetime


class DecisionReportDetailResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    stock_id: int
    pipeline_run_id: UUID
    action: str
    confidence: Decimal
    reasoning: str
    technical_summary: dict[str, Any]
    news_summary: dict[str, Any]
    memory_references: dict[str, Any] | None
    portfolio_state: dict[str, Any]
    outcome_pnl: Decimal | None
    outcome_benchmark_delta: Decimal | None
    outcome_assessed_at: datetime | None
    is_backtest: bool
    backtest_run_id: UUID | None
    created_at: datetime
    context_items: list[DecisionContextItemResponse] = []
