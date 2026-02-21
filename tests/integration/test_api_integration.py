"""Integration tests for API routes against a mocked app."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from tradeagent.core.types import PipelineStatus


def _make_app():
    """Create app with all state mocked."""
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


# ── Health ───────────────────────────────────────────────────


async def test_health_endpoint():
    """GET /api/health should return 200 with status field."""
    app = _make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert "status" in body


# ── Pipeline ─────────────────────────────────────────────────


async def test_pipeline_status_endpoint():
    """GET /api/pipeline/status should return current status."""
    app = _make_app()
    app.state.pipeline_status = PipelineStatus.SUCCESS

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/pipeline/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUCCESS"


async def test_pipeline_trigger_returns_202():
    """Trigger pipeline should return 202."""
    app = _make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/pipeline/run")
        assert response.status_code == 202
        body = response.json()
        assert "message" in body


# ── Backtest ─────────────────────────────────────────────────


async def test_backtest_trigger_and_poll_flow():
    """Full flow: trigger backtest, then poll for progress."""
    app = _make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Trigger
        response = await client.post("/api/backtest/run", json={
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 50000,
        })
        assert response.status_code == 202
        body = response.json()
        run_id = body["backtest_run_id"]

        # Poll (should be RUNNING since we just started)
        response = await client.get(f"/api/backtest/{run_id}")
        assert response.status_code == 200


# ── Error format ─────────────────────────────────────────────


async def test_validation_error_format():
    """Invalid request body should return standard error format."""
    app = _make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/backtest/run", json={
            "start_date": "not-a-date",
            "end_date": "2024-03-01",
        })

    assert response.status_code in (400, 422)
    body = response.json()
    assert "error" in body
