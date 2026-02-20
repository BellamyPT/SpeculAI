"""Unit tests for trades API routes."""

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


def _make_mock_trade(
    trade_id: int = 1,
    stock_id: int = 1,
    ticker: str = "AAPL",
    side: str = "BUY",
    qty: str = "10",
    price: str = "152.50",
) -> MagicMock:
    """Return a MagicMock that mimics a Trade ORM object.

    The Trade ORM model has no 'ticker' column — the route reads it from
    trade.stock.ticker after model_validate. We set trade.ticker = None so
    Pydantic's from_attributes validation does not receive a MagicMock object
    for that optional field.
    """
    trade = MagicMock()
    trade.id = trade_id
    trade.stock_id = stock_id
    # Explicitly set ticker=None on the trade mock itself so pydantic sees None
    # (the route overwrites this with trade.stock.ticker after model_validate)
    trade.ticker = None
    trade.side = side
    trade.quantity = Decimal(qty)
    trade.price = Decimal(price)
    trade.total_value = (Decimal(qty) * Decimal(price)).quantize(Decimal("0.01"))
    trade.currency = "EUR"
    trade.broker_order_id = f"broker-{trade_id}"
    trade.status = "FILLED"
    trade.executed_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    trade.is_backtest = False
    trade.backtest_run_id = None
    trade.decision_report_id = None
    trade.created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    trade.stock = MagicMock()
    trade.stock.ticker = ticker
    return trade


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("tradeagent.api.routes.trades.TradeRepository")
async def test_list_trades(MockTradeRepo):
    """GET /api/trades should return a paginated list of trades."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    trades = [
        _make_mock_trade(trade_id=1, ticker="AAPL"),
        _make_mock_trade(trade_id=2, ticker="MSFT", side="SELL"),
    ]
    MockTradeRepo.get_history = AsyncMock(return_value=(trades, 2))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/trades")

    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "pagination" in body
    assert len(body["data"]) == 2
    assert body["pagination"]["total"] == 2


@patch("tradeagent.api.routes.trades.TradeRepository")
async def test_filter_by_ticker(MockTradeRepo):
    """?ticker=AAPL should pass ticker='AAPL' to TradeRepository.get_history."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    aapl_trade = _make_mock_trade(ticker="AAPL")
    MockTradeRepo.get_history = AsyncMock(return_value=([aapl_trade], 1))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/trades?ticker=AAPL")

    assert response.status_code == 200
    call_kwargs = MockTradeRepo.get_history.call_args[1]
    assert call_kwargs["ticker"] == "AAPL"


@patch("tradeagent.api.routes.trades.TradeRepository")
async def test_filter_by_side(MockTradeRepo):
    """?side=BUY should pass side='BUY' to TradeRepository.get_history."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    MockTradeRepo.get_history = AsyncMock(return_value=([], 0))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/trades?side=BUY")

    assert response.status_code == 200
    call_kwargs = MockTradeRepo.get_history.call_args[1]
    assert call_kwargs["side"] == "BUY"


@patch("tradeagent.api.routes.trades.TradeRepository")
async def test_pagination(MockTradeRepo):
    """limit=10&offset=5 should be reflected in the pagination metadata."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    trades = [_make_mock_trade(trade_id=i) for i in range(6, 16)]
    MockTradeRepo.get_history = AsyncMock(return_value=(trades, 50))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/trades?limit=10&offset=5")

    assert response.status_code == 200
    body = response.json()
    pagination = body["pagination"]
    assert pagination["limit"] == 10
    assert pagination["offset"] == 5
    assert pagination["total"] == 50
    assert pagination["has_more"] is True


@patch("tradeagent.api.routes.trades.TradeRepository")
async def test_pagination_no_more(MockTradeRepo):
    """has_more should be False when offset+limit >= total."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    trades = [_make_mock_trade()]
    MockTradeRepo.get_history = AsyncMock(return_value=(trades, 5))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/trades?limit=50&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["has_more"] is False


@patch("tradeagent.api.routes.trades.TradeRepository")
async def test_trade_response_has_ticker(MockTradeRepo):
    """Each trade in the response should include the ticker field."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    trade = _make_mock_trade(ticker="NVDA")
    MockTradeRepo.get_history = AsyncMock(return_value=([trade], 1))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/trades")

    body = response.json()
    assert body["data"][0]["ticker"] == "NVDA"


@patch("tradeagent.api.routes.trades.TradeRepository")
async def test_empty_trades_list(MockTradeRepo):
    """Empty trade history should return data=[] and total=0."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    MockTradeRepo.get_history = AsyncMock(return_value=([], 0))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/trades")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["pagination"]["total"] == 0
    assert body["pagination"]["has_more"] is False
