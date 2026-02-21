"""Backtest API routes — trigger and poll backtest runs."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from tradeagent.core.types import BacktestStatus
from tradeagent.schemas.backtest import (
    BacktestMetricsResponse,
    BacktestProgressResponse,
    BacktestTriggerRequest,
    EquityCurvePoint,
)
from tradeagent.services.backtest import BacktestConfig, BacktestService

router = APIRouter()

MAX_RANGE_YEARS = 5


async def _run_backtest(app_state, config: BacktestConfig) -> None:
    """Background task that runs a backtest and stores the result."""
    try:
        service = BacktestService(
            session_factory=app_state.session_factory,
            settings=app_state.settings,
        )
        result = await service.run(config)
        app_state.backtest_result = result
        app_state.backtest_status = result.status
    except Exception:
        app_state.backtest_status = BacktestStatus.FAILED


@router.post("/backtest/run", status_code=202, response_model=None)
async def trigger_backtest(
    request: Request,
    body: BacktestTriggerRequest,
    background_tasks: BackgroundTasks,
) -> BacktestProgressResponse | JSONResponse:
    """Start a backtest run. Returns 202 Accepted or 409 if already running."""
    app_state = request.app.state

    # Check if already running
    if getattr(app_state, "backtest_status", None) == BacktestStatus.RUNNING:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "BACKTEST_ALREADY_RUNNING",
                    "message": "A backtest is already in progress",
                }
            },
        )

    # Validate range <= MAX_RANGE_YEARS
    today = date.today()
    if body.end_date > today:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "end_date cannot be in the future",
                }
            },
        )

    range_days = (body.end_date - body.start_date).days
    if range_days > MAX_RANGE_YEARS * 365:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Date range cannot exceed {MAX_RANGE_YEARS} years",
                }
            },
        )

    config = BacktestConfig(
        start_date=body.start_date,
        end_date=body.end_date,
        initial_capital=body.initial_capital,
    )

    # Initialize state
    app_state.backtest_status = BacktestStatus.RUNNING
    app_state.backtest_result = None

    background_tasks.add_task(_run_backtest, app_state, config)

    from uuid import uuid4
    from datetime import datetime, timezone

    return BacktestProgressResponse(
        backtest_run_id=uuid4(),
        status=BacktestStatus.RUNNING,
        current_day=0,
        total_days=0,
        started_at=datetime.now(tz=timezone.utc),
    )


@router.get("/backtest/{run_id}", response_model=None)
async def get_backtest_progress(
    request: Request,
    run_id: str,
) -> BacktestProgressResponse | JSONResponse:
    """Return backtest progress or final results."""
    app_state = request.app.state
    result = getattr(app_state, "backtest_result", None)

    if result is None:
        # Check if running
        status = getattr(app_state, "backtest_status", None)
        if status == BacktestStatus.RUNNING:
            from datetime import datetime, timezone

            return BacktestProgressResponse(
                backtest_run_id=run_id,
                status=BacktestStatus.RUNNING,
                current_day=0,
                total_days=0,
                started_at=datetime.now(tz=timezone.utc),
            )
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Backtest {run_id} not found",
                }
            },
        )

    metrics_response = None
    if result.metrics:
        metrics_response = BacktestMetricsResponse(
            total_return_pct=result.metrics.total_return_pct,
            annualized_return_pct=result.metrics.annualized_return_pct,
            max_drawdown_pct=result.metrics.max_drawdown_pct,
            sharpe_ratio=result.metrics.sharpe_ratio,
            win_rate_pct=result.metrics.win_rate_pct,
            total_trades=result.metrics.total_trades,
            avg_holding_days=result.metrics.avg_holding_days,
            benchmark_returns=result.metrics.benchmark_returns,
        )

    equity_curve = None
    if result.equity_curve:
        equity_curve = [
            EquityCurvePoint(date=p["date"], value=p["value"])
            for p in result.equity_curve
        ]

    return BacktestProgressResponse(
        backtest_run_id=result.backtest_run_id,
        status=result.status,
        current_day=result.current_day,
        total_days=result.total_days,
        started_at=result.started_at,
        completed_at=result.completed_at,
        metrics=metrics_response,
        equity_curve=equity_curve,
        errors=result.errors,
    )
