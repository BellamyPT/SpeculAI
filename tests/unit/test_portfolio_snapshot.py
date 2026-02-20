"""Unit tests for PortfolioSnapshotService."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tradeagent.config import Settings
from tradeagent.services.portfolio_snapshot import PortfolioSnapshotService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


def _make_mock_position(
    pos_id: int,
    stock_id: int,
    qty: str,
    avg_price: str,
) -> MagicMock:
    pos = MagicMock()
    pos.id = pos_id
    pos.stock_id = stock_id
    pos.quantity = Decimal(qty)
    pos.avg_price = Decimal(avg_price)
    pos.currency = "EUR"
    pos.opened_at = datetime(2024, 1, 10, tzinfo=timezone.utc)
    pos.status = "OPEN"
    pos.stock = MagicMock(ticker=f"STOCK{stock_id}")
    return pos


def _make_mock_price(close: str) -> MagicMock:
    p = MagicMock()
    p.close = Decimal(close)
    return p


def _make_mock_snapshot(total_value: str) -> MagicMock:
    snap = MagicMock()
    snap.id = 1
    snap.total_value = Decimal(total_value)
    return snap


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("tradeagent.services.portfolio_snapshot.PortfolioRepository")
@patch("tradeagent.services.portfolio_snapshot.StockRepository")
async def test_snapshot_creation(MockStockRepo, MockPortfolioRepo, settings: Settings):
    """create_daily_snapshot should call PortfolioRepository.create_snapshot with computed values."""
    mock_session = _make_mock_session()

    pos = _make_mock_position(pos_id=1, stock_id=1, qty="10", avg_price="145.00")
    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[pos])
    MockPortfolioRepo.get_latest_snapshot = AsyncMock(return_value=None)
    MockPortfolioRepo.bulk_create_position_snapshots = AsyncMock(return_value=[])

    mock_snap = _make_mock_snapshot("48525.0000")
    mock_snap.id = 99
    MockPortfolioRepo.create_snapshot = AsyncMock(return_value=mock_snap)

    MockStockRepo.get_latest_price = AsyncMock(return_value=_make_mock_price("152.50"))

    await PortfolioSnapshotService.create_daily_snapshot(mock_session, settings)

    assert MockPortfolioRepo.create_snapshot.called
    call_kwargs = MockPortfolioRepo.create_snapshot.call_args[1]
    # total_value = cash + invested = (50000 - 1450) + 1525 = 50075
    assert call_kwargs["total_value"] == Decimal("50075.0000")
    assert call_kwargs["cash"] == Decimal("48550.0000")
    assert call_kwargs["invested"] == Decimal("1525.0000")
    assert call_kwargs["num_positions"] == 1


@patch("tradeagent.services.portfolio_snapshot.PortfolioRepository")
@patch("tradeagent.services.portfolio_snapshot.StockRepository")
async def test_daily_pnl_computation(MockStockRepo, MockPortfolioRepo, settings: Settings):
    """daily_pnl should be current total_value minus previous snapshot total_value."""
    mock_session = _make_mock_session()

    pos = _make_mock_position(pos_id=1, stock_id=1, qty="10", avg_price="145.00")
    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[pos])

    # Previous snapshot: total was 49000
    prev_snap = _make_mock_snapshot("49000.0000")
    MockPortfolioRepo.get_latest_snapshot = AsyncMock(return_value=prev_snap)
    MockPortfolioRepo.bulk_create_position_snapshots = AsyncMock(return_value=[])

    mock_snap = _make_mock_snapshot("50075.0000")
    mock_snap.id = 100
    MockPortfolioRepo.create_snapshot = AsyncMock(return_value=mock_snap)

    MockStockRepo.get_latest_price = AsyncMock(return_value=_make_mock_price("152.50"))

    await PortfolioSnapshotService.create_daily_snapshot(mock_session, settings)

    call_kwargs = MockPortfolioRepo.create_snapshot.call_args[1]
    # daily_pnl = 50075 - 49000 = 1075
    assert call_kwargs["daily_pnl"] == Decimal("1075.0000")


@patch("tradeagent.services.portfolio_snapshot.PortfolioRepository")
@patch("tradeagent.services.portfolio_snapshot.StockRepository")
async def test_cumulative_pnl(MockStockRepo, MockPortfolioRepo, settings: Settings):
    """cumulative_pnl_pct should be (total_value - initial_capital) / initial_capital * 100."""
    mock_session = _make_mock_session()

    pos = _make_mock_position(pos_id=1, stock_id=1, qty="10", avg_price="100.00")
    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[pos])
    MockPortfolioRepo.get_latest_snapshot = AsyncMock(return_value=None)
    MockPortfolioRepo.bulk_create_position_snapshots = AsyncMock(return_value=[])

    mock_snap = MagicMock()
    mock_snap.id = 101
    mock_snap.total_value = Decimal("55000.0000")
    MockPortfolioRepo.create_snapshot = AsyncMock(return_value=mock_snap)

    # current_price = 600, qty = 10 → invested = 6000
    # cost_basis = 10 * 100 = 1000
    # cash = 50000 - 1000 = 49000
    # total_value = 49000 + 6000 = 55000
    # cumulative_pnl_pct = (55000 - 50000) / 50000 * 100 = 10.0
    MockStockRepo.get_latest_price = AsyncMock(return_value=_make_mock_price("600.00"))

    await PortfolioSnapshotService.create_daily_snapshot(mock_session, settings)

    call_kwargs = MockPortfolioRepo.create_snapshot.call_args[1]
    assert call_kwargs["cumulative_pnl_pct"] == Decimal("10.0000")


@patch("tradeagent.services.portfolio_snapshot.PortfolioRepository")
@patch("tradeagent.services.portfolio_snapshot.StockRepository")
async def test_position_snapshots_created(MockStockRepo, MockPortfolioRepo, settings: Settings):
    """bulk_create_position_snapshots should be called with one entry per open position."""
    mock_session = _make_mock_session()

    positions = [
        _make_mock_position(pos_id=1, stock_id=1, qty="10", avg_price="145.00"),
        _make_mock_position(pos_id=2, stock_id=2, qty="5", avg_price="300.00"),
    ]
    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=positions)
    MockPortfolioRepo.get_latest_snapshot = AsyncMock(return_value=None)

    mock_snap = MagicMock()
    mock_snap.id = 55
    MockPortfolioRepo.create_snapshot = AsyncMock(return_value=mock_snap)
    MockPortfolioRepo.bulk_create_position_snapshots = AsyncMock(return_value=[])

    MockStockRepo.get_latest_price = AsyncMock(return_value=_make_mock_price("150.00"))

    await PortfolioSnapshotService.create_daily_snapshot(mock_session, settings)

    assert MockPortfolioRepo.bulk_create_position_snapshots.called
    call_args = MockPortfolioRepo.bulk_create_position_snapshots.call_args[0]
    position_snapshots = call_args[1]
    assert len(position_snapshots) == 2
    # Each entry should reference the created snapshot id
    for snap_data in position_snapshots:
        assert snap_data["portfolio_snapshot_id"] == 55


@patch("tradeagent.services.portfolio_snapshot.PortfolioRepository")
@patch("tradeagent.services.portfolio_snapshot.StockRepository")
async def test_snapshot_no_positions(MockStockRepo, MockPortfolioRepo, settings: Settings):
    """Snapshot with no open positions should record total_value = initial_capital."""
    mock_session = _make_mock_session()

    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[])
    MockPortfolioRepo.get_latest_snapshot = AsyncMock(return_value=None)
    MockPortfolioRepo.bulk_create_position_snapshots = AsyncMock(return_value=[])

    mock_snap = MagicMock()
    mock_snap.id = 200
    MockPortfolioRepo.create_snapshot = AsyncMock(return_value=mock_snap)

    await PortfolioSnapshotService.create_daily_snapshot(mock_session, settings)

    call_kwargs = MockPortfolioRepo.create_snapshot.call_args[1]
    assert call_kwargs["total_value"] == Decimal("50000.0000")
    assert call_kwargs["cash"] == Decimal("50000.0000")
    assert call_kwargs["invested"] == Decimal("0")
    assert call_kwargs["num_positions"] == 0


@patch("tradeagent.services.portfolio_snapshot.PortfolioRepository")
@patch("tradeagent.services.portfolio_snapshot.StockRepository")
async def test_falls_back_to_avg_price_when_no_market_price(
    MockStockRepo, MockPortfolioRepo, settings: Settings
):
    """If no latest price is available, avg_price should be used as current_price."""
    mock_session = _make_mock_session()

    pos = _make_mock_position(pos_id=1, stock_id=1, qty="10", avg_price="145.00")
    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[pos])
    MockPortfolioRepo.get_latest_snapshot = AsyncMock(return_value=None)
    MockPortfolioRepo.bulk_create_position_snapshots = AsyncMock(return_value=[])

    mock_snap = MagicMock()
    mock_snap.id = 300
    MockPortfolioRepo.create_snapshot = AsyncMock(return_value=mock_snap)

    # No market price available
    MockStockRepo.get_latest_price = AsyncMock(return_value=None)

    await PortfolioSnapshotService.create_daily_snapshot(mock_session, settings)

    call_kwargs = MockPortfolioRepo.create_snapshot.call_args[1]
    # current_price = avg_price = 145, qty = 10 → invested = 1450
    # cost_basis = 10 * 145 = 1450
    # cash = 50000 - 1450 = 48550
    # total_value = 48550 + 1450 = 50000
    assert call_kwargs["total_value"] == Decimal("50000.0000")
    assert call_kwargs["invested"] == Decimal("1450.0000")
