from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tradeagent.core.exceptions import TradeAgentError
from tradeagent.main import create_app


@pytest.fixture
def mock_session():
    """Create a mock async session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def app(mock_session):
    """Create a FastAPI app with mocked database session."""
    application = create_app()

    factory = MagicMock(spec=async_sessionmaker)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = ctx

    application.state.session_factory = factory
    application.state.engine = AsyncMock()
    application.state.settings = MagicMock()

    return application


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_ok(self, client, mock_session):
        """Health endpoint returns ok when DB is connected."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["last_pipeline_run"] is None
        assert data["last_pipeline_status"] is None

    def test_health_degraded_when_db_fails(self, client, mock_session):
        """Health endpoint returns degraded when DB is unreachable."""
        mock_session.execute = AsyncMock(side_effect=Exception("connection refused"))

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"

    def test_health_with_pipeline_data(self, client, mock_session):
        """Health endpoint returns last pipeline run info."""
        from datetime import datetime

        mock_report = MagicMock()
        mock_report.created_at = datetime(2025, 1, 15, 10, 30, 0)
        mock_report.action = "BUY"

        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = mock_report

        # First call: SELECT 1, second call: DecisionReport query
        mock_session.execute = AsyncMock(side_effect=[MagicMock(), select_result])

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["last_pipeline_run"] == "2025-01-15T10:30:00"
        assert data["last_pipeline_status"] == "BUY"


class TestCORS:
    def test_cors_allowed_origin(self, client):
        """CORS headers present for allowed origins."""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_cors_disallowed_origin(self, client):
        """CORS headers absent for disallowed origins."""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in response.headers


class TestExceptionHandlers:
    def test_tradeagent_error_returns_400(self, app, client):
        """TradeAgentError subclass returns 400 with structured error."""

        @app.get("/api/test-error")
        async def raise_error():
            raise TradeAgentError("something went wrong")

        response = client.get("/api/test-error")

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "TRADEAGENTERROR"
        assert data["error"]["message"] == "something went wrong"

    def test_unhandled_error_returns_500(self, app):
        """Unhandled exception returns 500 with generic message."""

        @app.get("/api/test-crash")
        async def raise_crash():
            raise RuntimeError("unexpected failure")

        with TestClient(app, raise_server_exceptions=False) as c:
            response = c.get("/api/test-crash")

        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "INTERNAL_ERROR"
        assert data["error"]["message"] == "An unexpected error occurred"
        # Must NOT contain the real error message
        assert "unexpected failure" not in str(data)

    def test_validation_error_returns_400(self, app, client):
        """Invalid query parameters return 400 with field details."""
        from fastapi import Query

        @app.get("/api/test-validate")
        async def validated(count: int = Query()):
            return {"count": count}

        response = client.get("/api/test-validate?count=not_a_number")

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["details"] is not None
        assert len(data["error"]["details"]) > 0
