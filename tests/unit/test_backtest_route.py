"""Unit tests for backtest API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from tradeagent.core.types import BacktestStatus
from tradeagent.services.backtest import BacktestResult, BacktestConfig


def _make_app():
    """Create a fresh app instance with app state pre-populated."""
    from tradeagent.main import create_app

    app = create_app()
    app.state.pipeline_status = None
    app.state.last_pipeline_run = None
    app.state.backtest_status = None
    app.state.backtest_result = None
    app.state.pipeline_service = AsyncMock()
    app.state.settings = MagicMock()
    app.state.settings.portfolio.initial_capital = 50000.0
    app.state.settings.benchmarks = []

    mock_session = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory = MagicMock(return_value=mock_ctx)
    app.state.session_factory = mock_session_factory
    return app


async def test_trigger_returns_202():
    """POST /api/backtest/run with valid params should return 202."""
    app = _make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/backtest/run", json={
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 50000,
        })

    assert response.status_code == 202
    body = response.json()
    assert "backtest_run_id" in body
    assert body["status"] == "RUNNING"


async def test_trigger_returns_409_when_running():
    """POST /api/backtest/run when already running should return 409."""
    app = _make_app()
    app.state.backtest_status = BacktestStatus.RUNNING

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/backtest/run", json={
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
        })

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "BACKTEST_ALREADY_RUNNING"


async def test_trigger_returns_400_future_date():
    """POST /api/backtest/run with future end_date should return 400."""
    app = _make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/backtest/run", json={
            "start_date": "2024-01-01",
            "end_date": "2099-12-31",
        })

    assert response.status_code == 400


async def test_trigger_returns_400_invalid_range():
    """POST /api/backtest/run with >5 year range should return 400."""
    app = _make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/backtest/run", json={
            "start_date": "2015-01-01",
            "end_date": "2025-12-31",
        })

    # Might be 400 for range or for future date — both are acceptable
    assert response.status_code == 400


async def test_trigger_returns_400_start_after_end():
    """POST /api/backtest/run with start > end should return 400 (pydantic validation)."""
    app = _make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/backtest/run", json={
            "start_date": "2024-06-01",
            "end_date": "2024-01-01",
        })

    assert response.status_code == 400


async def test_get_progress_completed():
    """GET /api/backtest/{run_id} for a completed backtest should return metrics."""
    app = _make_app()
    run_id = uuid4()

    from tradeagent.services.backtest import BacktestMetrics

    app.state.backtest_result = BacktestResult(
        backtest_run_id=run_id,
        status=BacktestStatus.COMPLETED,
        config=BacktestConfig(
            start_date=__import__("datetime").date(2024, 1, 1),
            end_date=__import__("datetime").date(2024, 3, 1),
        ),
        metrics=BacktestMetrics(
            total_return_pct=5.2,
            annualized_return_pct=15.1,
            max_drawdown_pct=3.5,
            sharpe_ratio=1.8,
            win_rate_pct=60.0,
            total_trades=12,
            avg_holding_days=8.5,
        ),
        equity_curve=[
            {"date": "2024-01-02", "value": 50000},
            {"date": "2024-01-03", "value": 50250},
        ],
        current_day=40,
        total_days=40,
        started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2024, 1, 1, 0, 5, tzinfo=timezone.utc),
    )
    app.state.backtest_status = BacktestStatus.COMPLETED

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/backtest/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["metrics"] is not None
    assert body["metrics"]["total_return_pct"] == 5.2
    assert body["equity_curve"] is not None
    assert len(body["equity_curve"]) == 2


async def test_get_progress_404():
    """GET /api/backtest/{run_id} with no result should return 404."""
    app = _make_app()
    app.state.backtest_status = None
    app.state.backtest_result = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/backtest/{uuid4()}")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"


async def test_get_progress_running():
    """GET /api/backtest/{run_id} while running should return RUNNING status."""
    app = _make_app()
    app.state.backtest_status = BacktestStatus.RUNNING
    app.state.backtest_result = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/backtest/{uuid4()}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RUNNING"
