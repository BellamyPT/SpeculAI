"""Unit tests for SimulatedBroker."""

from __future__ import annotations

from decimal import Decimal

from tradeagent.adapters.base import OrderRequest
from tradeagent.adapters.broker.simulated import SimulatedBroker


def _make_order(ticker: str, side: str, qty: str) -> OrderRequest:
    return OrderRequest(ticker=ticker, side=side, quantity=Decimal(qty))


async def test_fills_at_next_open_price():
    """Orders should fill at the next-day open price, not current close."""
    broker = SimulatedBroker(initial_capital=Decimal("100000"))
    broker.set_next_open_prices({"AAPL": Decimal("151.00")})

    result = await broker.place_order(_make_order("AAPL", "BUY", "10"))

    assert result.status == "FILLED"
    assert result.filled_price == Decimal("151.00")
    assert result.filled_quantity == Decimal("10")


async def test_cash_tracking_buy():
    """BUY order should deduct cash by quantity * fill price."""
    broker = SimulatedBroker(initial_capital=Decimal("50000"))
    broker.set_next_open_prices({"AAPL": Decimal("100.00")})

    await broker.place_order(_make_order("AAPL", "BUY", "10"))

    assert broker.cash == Decimal("49000")  # 50000 - 10 * 100


async def test_cash_tracking_sell():
    """SELL order should add cash by quantity * fill price."""
    broker = SimulatedBroker(initial_capital=Decimal("50000"))
    broker.set_next_open_prices({"AAPL": Decimal("100.00")})

    await broker.place_order(_make_order("AAPL", "BUY", "10"))
    broker.set_next_open_prices({"AAPL": Decimal("120.00")})
    await broker.place_order(_make_order("AAPL", "SELL", "10"))

    assert broker.cash == Decimal("50200")  # 49000 + 10 * 120


async def test_position_tracking():
    """BUY should create a position visible in get_positions."""
    broker = SimulatedBroker(initial_capital=Decimal("50000"))
    broker.set_next_open_prices({"AAPL": Decimal("150.00")})
    await broker.place_order(_make_order("AAPL", "BUY", "5"))

    positions = await broker.get_positions()

    assert len(positions) == 1
    assert positions[0].ticker == "AAPL"
    assert positions[0].quantity == Decimal("5")


async def test_sell_reduces_position():
    """Partial sell should reduce position quantity."""
    broker = SimulatedBroker(initial_capital=Decimal("50000"))
    broker.set_next_open_prices({"AAPL": Decimal("150.00")})
    await broker.place_order(_make_order("AAPL", "BUY", "10"))
    await broker.place_order(_make_order("AAPL", "SELL", "4"))

    positions = await broker.get_positions()

    assert len(positions) == 1
    assert positions[0].quantity == Decimal("6")


async def test_sell_removes_position():
    """Selling entire position should remove it."""
    broker = SimulatedBroker(initial_capital=Decimal("50000"))
    broker.set_next_open_prices({"MSFT": Decimal("300.00")})
    await broker.place_order(_make_order("MSFT", "BUY", "5"))
    await broker.place_order(_make_order("MSFT", "SELL", "5"))

    positions = await broker.get_positions()
    assert len(positions) == 0


async def test_portfolio_value():
    """get_portfolio_value should return cash + positions at market prices."""
    broker = SimulatedBroker(initial_capital=Decimal("50000"))
    broker.set_next_open_prices({"AAPL": Decimal("100.00")})
    await broker.place_order(_make_order("AAPL", "BUY", "10"))

    # Update prices for valuation
    broker.set_next_open_prices({"AAPL": Decimal("110.00")})

    value = broker.get_portfolio_value()
    # cash = 50000 - 10*100 = 49000, positions = 10*110 = 1100
    assert value == Decimal("50100")


async def test_insufficient_cash_fails():
    """Buying more than cash allows should fail."""
    broker = SimulatedBroker(initial_capital=Decimal("1000"))
    broker.set_next_open_prices({"AAPL": Decimal("200.00")})

    result = await broker.place_order(_make_order("AAPL", "BUY", "10"))

    assert result.status == "FAILED"
    assert "Insufficient cash" in (result.error_message or "")


async def test_no_next_open_price_fails():
    """Order for a ticker without set next-open price should fail."""
    broker = SimulatedBroker(initial_capital=Decimal("50000"))

    result = await broker.place_order(_make_order("AAPL", "BUY", "10"))

    assert result.status == "FAILED"
    assert "No next-open price" in (result.error_message or "")


async def test_reset():
    """reset() should clear all state and restore initial capital."""
    broker = SimulatedBroker(initial_capital=Decimal("50000"))
    broker.set_next_open_prices({"AAPL": Decimal("100.00")})
    await broker.place_order(_make_order("AAPL", "BUY", "10"))

    broker.reset()

    assert broker.cash == Decimal("50000")
    positions = await broker.get_positions()
    assert len(positions) == 0


async def test_get_order_status_existing():
    """get_order_status for a placed order should return FILLED."""
    broker = SimulatedBroker(initial_capital=Decimal("50000"))
    broker.set_next_open_prices({"AAPL": Decimal("100.00")})
    placed = await broker.place_order(_make_order("AAPL", "BUY", "5"))

    status = await broker.get_order_status(placed.broker_order_id)
    assert status.status == "FILLED"


async def test_get_order_status_missing():
    """get_order_status for unknown order should return FAILED."""
    broker = SimulatedBroker()
    status = await broker.get_order_status("nonexistent")
    assert status.status == "FAILED"


async def test_get_instruments_returns_empty():
    """get_instruments should return empty list."""
    broker = SimulatedBroker()
    instruments = await broker.get_instruments()
    assert instruments == []


async def test_multiple_buys_average_price():
    """Multiple BUY orders should update average price."""
    broker = SimulatedBroker(initial_capital=Decimal("100000"))
    broker.set_next_open_prices({"AAPL": Decimal("100.00")})
    await broker.place_order(_make_order("AAPL", "BUY", "10"))

    broker.set_next_open_prices({"AAPL": Decimal("120.00")})
    await broker.place_order(_make_order("AAPL", "BUY", "10"))

    positions = await broker.get_positions()
    assert len(positions) == 1
    assert positions[0].quantity == Decimal("20")
    # avg = (10*100 + 10*120) / 20 = 110
    assert positions[0].avg_price == Decimal("110.0000")
