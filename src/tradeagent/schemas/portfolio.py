from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PositionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    stock_id: int
    ticker: str | None = None
    quantity: Decimal
    avg_price: Decimal
    current_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    weight_pct: Decimal | None = None
    currency: str
    opened_at: datetime
    closed_at: datetime | None
    status: str


class PositionSnapshotResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    portfolio_snapshot_id: int
    stock_id: int
    quantity: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    weight_pct: Decimal


class PortfolioSnapshotResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    date: date
    total_value: Decimal
    cash: Decimal
    invested: Decimal
    daily_pnl: Decimal
    cumulative_pnl_pct: Decimal
    num_positions: int
    is_backtest: bool
    backtest_run_id: UUID | None


class PortfolioSummaryResponse(BaseModel):
    total_value: Decimal
    cash: Decimal
    invested: Decimal
    daily_pnl: Decimal
    cumulative_pnl_pct: Decimal
    num_positions: int
    positions: list[PositionResponse]


class BenchmarkSeries(BaseModel):
    symbol: str
    name: str
    data: list[dict]


class PortfolioPerformanceResponse(BaseModel):
    snapshots: list[PortfolioSnapshotResponse]
    benchmarks: list[BenchmarkSeries] = []
