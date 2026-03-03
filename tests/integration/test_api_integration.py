"""Integration tests for API routes against a mocked app."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from tradeagent.core.types import PipelineStatus


def _make_app():
    """Create app with all state mocked."""
    from tradeagent.main import create_app

    app = create_app()

    app.state.pipeline_status = None
    app.state.last_pipeline_run = None
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


