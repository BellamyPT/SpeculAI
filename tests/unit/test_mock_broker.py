"""Unit tests for MockBrokerAdapter."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tradeagent.adapters.base import OrderRequest
from tradeagent.adapters.broker.mock_broker import MockBrokerAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_order(ticker: str, side: str, qty: str) -> OrderRequest:
    return OrderRequest(ticker=ticker, side=side, quantity=Decimal(qty))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_immediate_fill():
    """place_order should immediately return FILLED status."""
    broker = MockBrokerAdapter()
    order = _make_order("AAPL", "BUY", "10")

    result = await broker.place_order(order)

    assert result.status == "FILLED"
    assert result.ticker == "AAPL"
    assert result.side == "BUY"
    assert result.filled_quantity == Decimal("10")
    assert result.filled_at is not None
    assert result.broker_order_id != ""


async def test_position_tracking():
    """A BUY order should create a position visible in get_positions."""
    broker = MockBrokerAdapter()
    broker.set_current_price("AAPL", Decimal("155.00"))
    await broker.place_order(_make_order("AAPL", "BUY", "5"))

    positions = await broker.get_positions()

    assert len(positions) == 1
    aapl = positions[0]
    assert aapl.ticker == "AAPL"
    assert aapl.quantity == Decimal("5")
    assert aapl.current_price == Decimal("155.00")


async def test_sell_reduces_position():
    """A SELL order for a partial quantity should reduce the existing position."""
    broker = MockBrokerAdapter()
    broker.set_current_price("AAPL", Decimal("150.00"))

    await broker.place_order(_make_order("AAPL", "BUY", "10"))
    await broker.place_order(_make_order("AAPL", "SELL", "4"))

    positions = await broker.get_positions()

    assert len(positions) == 1
    assert positions[0].quantity == Decimal("6")


async def test_sell_removes_position():
    """Selling the entire position quantity should remove it from tracking."""
    broker = MockBrokerAdapter()
    broker.set_current_price("MSFT", Decimal("300.00"))

    await broker.place_order(_make_order("MSFT", "BUY", "8"))
    await broker.place_order(_make_order("MSFT", "SELL", "8"))

    positions = await broker.get_positions()

    assert len(positions) == 0


async def test_set_current_price():
    """set_current_price should affect unrealized_pnl calculation in get_positions."""
    broker = MockBrokerAdapter()
    broker.set_current_price("AAPL", Decimal("100.00"))
    await broker.place_order(_make_order("AAPL", "BUY", "10"))

    # Price rises from 100 to 120
    broker.set_current_price("AAPL", Decimal("120.00"))
    positions = await broker.get_positions()

    assert len(positions) == 1
    pos = positions[0]
    assert pos.current_price == Decimal("120.00")
    # unrealized_pnl = (120 - 100) * 10 = 200
    assert pos.unrealized_pnl == Decimal("200.00")


async def test_reset():
    """reset() should clear all positions and orders."""
    broker = MockBrokerAdapter()
    broker.set_current_price("AAPL", Decimal("150.00"))
    await broker.place_order(_make_order("AAPL", "BUY", "10"))
    await broker.place_order(_make_order("MSFT", "BUY", "5"))

    broker.reset()

    positions = await broker.get_positions()
    assert positions == []


async def test_multiple_buys_average_price():
    """Multiple BUY orders should update the position's average price correctly."""
    broker = MockBrokerAdapter()
    broker.set_current_price("AAPL", Decimal("100.00"))
    await broker.place_order(_make_order("AAPL", "BUY", "10"))

    broker.set_current_price("AAPL", Decimal("120.00"))
    await broker.place_order(_make_order("AAPL", "BUY", "10"))

    positions = await broker.get_positions()
    assert len(positions) == 1
    pos = positions[0]
    assert pos.quantity == Decimal("20")
    # avg_price = (10*100 + 10*120) / 20 = 110
    assert pos.avg_price == Decimal("110.0000")


async def test_get_order_status_missing_order():
    """get_order_status for an unknown order_id should return FAILED."""
    broker = MockBrokerAdapter()
    result = await broker.get_order_status("nonexistent-order-id")

    assert result.status == "FAILED"
    assert result.error_message is not None


async def test_get_order_status_existing_order():
    """get_order_status for a placed order should return FILLED."""
    broker = MockBrokerAdapter()
    placed = await broker.place_order(_make_order("AAPL", "BUY", "3"))

    status = await broker.get_order_status(placed.broker_order_id)

    assert status.status == "FILLED"
    assert status.ticker == "AAPL"


async def test_multiple_tickers_tracked_independently():
    """Positions for different tickers should be tracked independently."""
    broker = MockBrokerAdapter()
    broker.set_current_price("AAPL", Decimal("150.00"))
    broker.set_current_price("MSFT", Decimal("300.00"))

    await broker.place_order(_make_order("AAPL", "BUY", "5"))
    await broker.place_order(_make_order("MSFT", "BUY", "3"))

    positions = await broker.get_positions()
    assert len(positions) == 2

    tickers = {p.ticker for p in positions}
    assert "AAPL" in tickers
    assert "MSFT" in tickers


async def test_get_instruments_returns_empty():
    """get_instruments should return an empty list (mock implementation)."""
    broker = MockBrokerAdapter()
    instruments = await broker.get_instruments()

    assert instruments == []
