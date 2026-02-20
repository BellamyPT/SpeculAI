"""Unit tests for portfolio API routes."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from tradeagent.api.dependencies import get_db_session
from tradeagent.config import Settings


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def _make_app_with_session(mock_session: AsyncMock):
    """Create a FastAPI app with the DB session dependency overridden."""
    from tradeagent.main import create_app

    app = create_app()

    async def _override_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _override_session

    settings = Settings()
    app.state.settings = settings
    app.state.pipeline_status = None
    app.state.last_pipeline_run = None
    app.state.pipeline_service = AsyncMock()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session_ctx)
    app.state.session_factory = mock_factory

    return app


def _make_mock_position(
    pos_id: int = 1,
    stock_id: int = 1,
    ticker: str = "AAPL",
    qty: str = "10",
    avg_price: str = "145.00",
) -> MagicMock:
    """Return a MagicMock mimicking a Position ORM object."""
    pos = MagicMock()
    pos.id = pos_id
    pos.stock_id = stock_id
    pos.quantity = Decimal(qty)
    pos.avg_price = Decimal(avg_price)
    pos.currency = "EUR"
    pos.opened_at = datetime(2024, 1, 10, tzinfo=timezone.utc)
    pos.closed_at = None
    pos.status = "OPEN"
    pos.stock = MagicMock()
    pos.stock.ticker = ticker
    return pos


def _make_mock_price(close: str = "152.50") -> MagicMock:
    p = MagicMock()
    p.close = Decimal(close)
    return p


def _make_mock_snapshot(
    snap_id: int = 1,
    total_value: str = "50500.00",
    cash: str = "49000.00",
    invested: str = "1500.00",
    daily_pnl: str = "500.0000",
    cumulative_pnl_pct: str = "1.0000",
    num_positions: int = 1,
) -> MagicMock:
    snap = MagicMock()
    snap.id = snap_id
    snap.date = date(2024, 1, 15)
    snap.total_value = Decimal(total_value)
    snap.cash = Decimal(cash)
    snap.invested = Decimal(invested)
    snap.daily_pnl = Decimal(daily_pnl)
    snap.cumulative_pnl_pct = Decimal(cumulative_pnl_pct)
    snap.num_positions = num_positions
    snap.is_backtest = False
    snap.backtest_run_id = None
    return snap


# ---------------------------------------------------------------------------
# Tests — /api/portfolio/summary
# ---------------------------------------------------------------------------


@patch("tradeagent.api.routes.portfolio.StockRepository")
@patch("tradeagent.api.routes.portfolio.PortfolioRepository")
async def test_summary_with_positions(MockPortfolioRepo, MockStockRepo):
    """Portfolio summary with an open position should return computed total_value."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    pos = _make_mock_position(pos_id=1, stock_id=1, ticker="AAPL", qty="10", avg_price="145.00")
    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[pos])
    MockPortfolioRepo.get_latest_snapshot = AsyncMock(return_value=None)
    MockStockRepo.get_latest_price = AsyncMock(return_value=_make_mock_price("152.50"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/portfolio/summary")

    assert response.status_code == 200
    body = response.json()
    assert "total_value" in body
    assert "positions" in body
    assert len(body["positions"]) == 1
    assert body["positions"][0]["ticker"] == "AAPL"
    # total_value = cash(50000 - 1450) + invested(1525) = 49075
    assert Decimal(str(body["total_value"])) > 0


@patch("tradeagent.api.routes.portfolio.StockRepository")
@patch("tradeagent.api.routes.portfolio.PortfolioRepository")
async def test_summary_empty_portfolio(MockPortfolioRepo, MockStockRepo):
    """Empty portfolio should return total_value equal to initial_capital."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[])
    MockPortfolioRepo.get_latest_snapshot = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/portfolio/summary")

    assert response.status_code == 200
    body = response.json()
    # With no positions, total_value = initial_capital = 50000
    assert Decimal(str(body["total_value"])) == Decimal("50000")
    assert body["num_positions"] == 0
    assert body["positions"] == []


@patch("tradeagent.api.routes.portfolio.StockRepository")
@patch("tradeagent.api.routes.portfolio.PortfolioRepository")
async def test_summary_initial_capital_fallback(MockPortfolioRepo, MockStockRepo):
    """When no previous snapshot exists, daily_pnl should be computed vs initial_capital."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[])
    MockPortfolioRepo.get_latest_snapshot = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/portfolio/summary")

    assert response.status_code == 200
    body = response.json()
    # daily_pnl = total_value - initial_capital; both are 50000, so 0
    assert Decimal(str(body["daily_pnl"])) == Decimal("0")


@patch("tradeagent.api.routes.portfolio.BenchmarkRepository")
@patch("tradeagent.api.routes.portfolio.PortfolioRepository")
async def test_performance_with_benchmarks(MockPortfolioRepo, MockBenchmarkRepo):
    """Performance endpoint should return snapshots and benchmarks arrays."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)
    # Inject a settings with one benchmark
    from tradeagent.config import BenchmarkItem
    app.state.settings.benchmarks = [BenchmarkItem(symbol="^GSPC", name="S&P 500")]

    snapshot = _make_mock_snapshot()
    MockPortfolioRepo.get_snapshots = AsyncMock(return_value=([snapshot], 1))

    mock_bm = MagicMock()
    mock_bm.id = 1
    mock_bm.symbol = "^GSPC"
    MockBenchmarkRepo.get_by_symbol = AsyncMock(return_value=mock_bm)

    bm_price_1 = MagicMock()
    bm_price_1.date = date(2024, 1, 10)
    bm_price_1.close = Decimal("4700.00")
    bm_price_2 = MagicMock()
    bm_price_2.date = date(2024, 1, 15)
    bm_price_2.close = Decimal("4750.00")
    MockBenchmarkRepo.get_prices = AsyncMock(return_value=([bm_price_1, bm_price_2], 2))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/portfolio/performance")

    assert response.status_code == 200
    body = response.json()
    assert "snapshots" in body
    assert "benchmarks" in body
    assert len(body["benchmarks"]) == 1
    assert body["benchmarks"][0]["symbol"] == "^GSPC"


@patch("tradeagent.api.routes.portfolio.StockRepository")
@patch("tradeagent.api.routes.portfolio.PortfolioRepository")
async def test_summary_with_snapshot_daily_pnl(MockPortfolioRepo, MockStockRepo):
    """daily_pnl should be computed as total_value minus latest snapshot total_value."""
    mock_session = AsyncMock()
    app = _make_app_with_session(mock_session)

    pos = _make_mock_position(qty="10", avg_price="145.00")
    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[pos])
    MockPortfolioRepo.get_latest_snapshot = AsyncMock(
        return_value=_make_mock_snapshot(total_value="50000.00")
    )
    MockStockRepo.get_latest_price = AsyncMock(return_value=_make_mock_price("152.50"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/portfolio/summary")

    assert response.status_code == 200
    body = response.json()
    # Snapshot total was 50000. Current total = 50000 - 1450 + 1525 = 50075
    # daily_pnl = 50075 - 50000 = 75
    assert Decimal(str(body["daily_pnl"])) == Decimal("75.0000")
