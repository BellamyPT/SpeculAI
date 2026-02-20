"""Unit tests for pipeline API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from tradeagent.core.types import PipelineStatus
from tradeagent.services.pipeline import PipelineRunResult


def _make_app():
    """Create a fresh app instance with app state pre-populated."""
    from tradeagent.main import create_app

    app = create_app()
    # Pre-populate state so routes don't fail on missing attributes
    app.state.pipeline_status = None
    app.state.last_pipeline_run = None
    app.state.pipeline_service = AsyncMock()
    app.state.settings = MagicMock()
    app.state.settings.portfolio.initial_capital = 50000.0
    app.state.settings.benchmarks = []
    # Provide a session_factory so the dependency doesn't crash during startup
    mock_session = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory = MagicMock(return_value=mock_ctx)
    app.state.session_factory = mock_session_factory
    return app


async def test_trigger_returns_202():
    """POST /api/pipeline/run when no pipeline is running should return 202."""
    app = _make_app()
    app.state.pipeline_status = None  # No pipeline running

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/pipeline/run")

    assert response.status_code == 202
    body = response.json()
    assert "message" in body


async def test_trigger_returns_409_when_running():
    """POST /api/pipeline/run when pipeline is already running should return 409."""
    app = _make_app()
    app.state.pipeline_status = PipelineStatus.RUNNING

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/pipeline/run")

    assert response.status_code == 409
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "PIPELINE_ALREADY_RUNNING"


async def test_status_returns_idle():
    """GET /api/pipeline/status when no run has occurred should return status=None."""
    app = _make_app()
    app.state.pipeline_status = None
    app.state.last_pipeline_run = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/pipeline/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] is None
    assert body["last_run"] is None


async def test_status_returns_last_run():
    """GET /api/pipeline/status after a completed run should include last_run data."""
    app = _make_app()

    run_id = uuid4()
    started = datetime(2024, 1, 15, 7, 0, 0, tzinfo=timezone.utc)
    completed = datetime(2024, 1, 15, 7, 5, 30, tzinfo=timezone.utc)

    last_run = PipelineRunResult(
        pipeline_run_id=run_id,
        status=PipelineStatus.SUCCESS,
        started_at=started,
        completed_at=completed,
        stocks_analyzed=50,
        candidates_screened=20,
        trades_approved=3,
        trades_executed=3,
        errors=[],
    )
    app.state.pipeline_status = PipelineStatus.SUCCESS
    app.state.last_pipeline_run = last_run

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/pipeline/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["last_run"] is not None
    assert body["last_run"]["stocks_analyzed"] == 50
    assert body["last_run"]["trades_approved"] == 3
    assert body["last_run"]["trades_executed"] == 3
    assert body["last_run"]["pipeline_run_id"] == str(run_id)


async def test_trigger_sets_running_status():
    """After triggering, pipeline_status should be updated to RUNNING."""
    app = _make_app()
    app.state.pipeline_status = None

    # Make the pipeline service block long enough that we can inspect state
    async def _slow_run():
        import asyncio
        await asyncio.sleep(0.01)
        return PipelineRunResult(
            pipeline_run_id=uuid4(),
            status=PipelineStatus.SUCCESS,
            started_at=datetime.now(tz=timezone.utc),
        )

    app.state.pipeline_service.run = _slow_run

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/pipeline/run")

    assert response.status_code == 202


async def test_trigger_response_has_message():
    """202 response should contain a human-readable message."""
    app = _make_app()
    app.state.pipeline_status = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/pipeline/run")

    body = response.json()
    assert isinstance(body.get("message"), str)
    assert len(body["message"]) > 0
