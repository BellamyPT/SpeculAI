"""Backtest API schemas."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class BacktestTriggerRequest(BaseModel):
    start_date: date
    end_date: date
    initial_capital: float = 50000.0

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v <= start:
            raise ValueError("end_date must be after start_date")
        return v

    @field_validator("initial_capital")
    @classmethod
    def positive_capital(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("initial_capital must be positive")
        return v


class BacktestMetricsResponse(BaseModel):
    total_return_pct: float
    annualized_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate_pct: float
    total_trades: int
    avg_holding_days: float
    benchmark_returns: dict[str, float] = {}


class EquityCurvePoint(BaseModel):
    date: str
    value: float


class BacktestProgressResponse(BaseModel):
    backtest_run_id: UUID
    status: str
    current_day: int
    total_days: int
    started_at: datetime
    completed_at: datetime | None = None
    metrics: BacktestMetricsResponse | None = None
    equity_curve: list[EquityCurvePoint] | None = None
    errors: list[str] = []
