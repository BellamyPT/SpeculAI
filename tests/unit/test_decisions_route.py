"""Unit tests for decisions API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from tradeagent.api.dependencies import get_db_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app_with_session(mock_session: AsyncMock):
    """Create a FastAPI app with the DB session dependency overridden."""
    from tradeagent.main import create_app

    app = create_app()

    async def _override_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _override_session

    from tradeagent.config import Settings
    app.state.settings = Settings()
    app.state.pipeline_status = None
    app.state.last_pipeline_run = None
    app.state.pipeline_service = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    app.state.session_factory = MagicMock(return_value=mock_ctx)

    return app


def _make_mock_report(
    report_id: int = 1,
    stock_id: int = 1,
    ticker: str = "AAPL",
    action: str = "BUY",
    confidence: str = "0.80",
) -> MagicMock:
    """Return a MagicMock that mimics a DecisionReport ORM object.

    DecisionReport has no 'ticker' column — the route reads it from report.stock.ticker
    after model_validate. Set report.ticker = None explicitly so Pydantic sees a valid
    optional string rather than a raw MagicMock during from_attributes validation.
    """
    report = MagicMock()
    report.id = report_id
    report.stock_id = stock_id
    report.pipeline_run_id = uuid4()
    report.action = action
    report.confidence = Decimal(confidence)
    # Set ticker=None so pydantic from_attributes validation gets None (a valid str | None)
    report.ticker = None
    report.reasoning = f"{action} signal on {ticker}: strong technical indicators"
    report.technical_summary = {"rsi": 40.0, "macd": {"direction": "bullish"}}
    report.news_summary = {"candidate_score": 0.75}
    report.memory_references = None
    report.portfolio_state = {"total_value": "50000", "cash_available": "48000"}
    report.is_backtest = False
    report.backtest_run_id = None
    report.created_at = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
    report.outcome_pnl = None
    report.outcome_benchmark_delta = None
    report.outcome_assessed_at = None
    report.stock = MagicMock()
    report.stock.ticker = ticker
    report.context_items = []
    return report


def _make_mock_context_item(item_id: int, report_id: int, ctx_type: str) -> MagicMock:
    item = MagicMock()
    item.id = item_id
    item.decision_report_id = report_id
    item.context_type = ctx_type
    item.source = f"indicators:AAPL" if ctx_type == "technical" else "Reuters"
    item.content = "Some context content"
    item.relevance_score = Decimal("0.85")
    item.created_at = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
    return item


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("tradeagent.api.routes.decisions.DecisionRepository")
async def test_list_decisions(MockDecisionRepo):
    """GET /api/decisions should return a paginated list of decision reports."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    reports = [
        _make_mock_report(report_id=1, ticker="AAPL", action="BUY"),
        _make_mock_report(report_id=2, ticker="MSFT", action="SELL"),
    ]
    MockDecisionRepo.get_list = AsyncMock(return_value=(reports, 2))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/decisions")

    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "pagination" in body
    assert len(body["data"]) == 2
    assert body["pagination"]["total"] == 2


@patch("tradeagent.api.routes.decisions.DecisionRepository")
async def test_filter_by_action(MockDecisionRepo):
    """?action=BUY should pass action='BUY' to DecisionRepository.get_list."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    MockDecisionRepo.get_list = AsyncMock(
        return_value=([_make_mock_report(action="BUY")], 1)
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/decisions?action=BUY")

    assert response.status_code == 200
    call_kwargs = MockDecisionRepo.get_list.call_args[1]
    assert call_kwargs["action"] == "BUY"


@patch("tradeagent.api.routes.decisions.DecisionRepository")
async def test_filter_by_confidence(MockDecisionRepo):
    """?min_confidence=0.7 should pass min_confidence=0.7 to get_list."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    MockDecisionRepo.get_list = AsyncMock(return_value=([], 0))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/decisions?min_confidence=0.7")

    assert response.status_code == 200
    call_kwargs = MockDecisionRepo.get_list.call_args[1]
    assert call_kwargs["min_confidence"] == pytest.approx(0.7)


@patch("tradeagent.api.routes.decisions.DecisionRepository")
async def test_detail_found(MockDecisionRepo):
    """GET /api/decisions/1 should return the full decision detail."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    report = _make_mock_report(report_id=1, ticker="AAPL")
    ctx_item = _make_mock_context_item(item_id=10, report_id=1, ctx_type="technical")
    report.context_items = [ctx_item]
    MockDecisionRepo.get_by_id = AsyncMock(return_value=report)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/decisions/1")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["action"] == "BUY"
    assert "context_items" in body
    assert len(body["context_items"]) == 1
    assert body["context_items"][0]["context_type"] == "technical"


@patch("tradeagent.api.routes.decisions.DecisionRepository")
async def test_detail_404(MockDecisionRepo):
    """GET /api/decisions/999 should return 404 when report not found."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    MockDecisionRepo.get_by_id = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/decisions/999")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"


@patch("tradeagent.api.routes.decisions.DecisionRepository")
async def test_decision_response_has_ticker(MockDecisionRepo):
    """Each decision in the list should include the ticker field."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    report = _make_mock_report(ticker="NVDA")
    MockDecisionRepo.get_list = AsyncMock(return_value=([report], 1))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/decisions")

    body = response.json()
    assert body["data"][0]["ticker"] == "NVDA"


@patch("tradeagent.api.routes.decisions.DecisionRepository")
async def test_empty_decisions_list(MockDecisionRepo):
    """Empty decisions list should return data=[] and total=0."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    MockDecisionRepo.get_list = AsyncMock(return_value=([], 0))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/decisions")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["pagination"]["total"] == 0


@patch("tradeagent.api.routes.decisions.DecisionRepository")
async def test_decisions_pagination_has_more(MockDecisionRepo):
    """Pagination has_more should be True when there are more records beyond offset+limit."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    reports = [_make_mock_report(report_id=i) for i in range(1, 11)]
    MockDecisionRepo.get_list = AsyncMock(return_value=(reports, 100))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/decisions?limit=10&offset=0")

    body = response.json()
    assert body["pagination"]["has_more"] is True
    assert body["pagination"]["total"] == 100
