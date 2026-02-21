"""Simulated broker adapter — fills at next-day-open for backtesting."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from tradeagent.adapters.base import (
    BrokerAdapter,
    BrokerInstrument,
    BrokerPosition,
    OrderRequest,
    OrderStatus,
)


class SimulatedBroker(BrokerAdapter):
    """Broker that fills at next-day open price for backtest realism.

    Unlike MockBrokerAdapter which fills immediately at current close,
    this broker requires ``set_next_open_prices()`` to be called each day
    so orders fill at the next trading day's open — avoiding lookahead bias.
    """

    def __init__(self, initial_capital: Decimal = Decimal("50000")) -> None:
        self._cash: Decimal = initial_capital
        self._initial_capital: Decimal = initial_capital
        self._positions: dict[str, dict] = {}  # ticker -> {quantity, avg_price}
        self._next_open_prices: dict[str, Decimal] = {}
        self._orders: dict[str, OrderStatus] = {}

    def set_next_open_prices(self, prices: dict[str, Decimal]) -> None:
        """Set next-day open prices used for fill simulation."""
        self._next_open_prices = prices

    async def place_order(self, order: OrderRequest) -> OrderStatus:
        """Fill order at next-day open price."""
        order_id = str(uuid4())
        fill_price = self._next_open_prices.get(order.ticker)

        if fill_price is None:
            return OrderStatus(
                broker_order_id=order_id,
                ticker=order.ticker,
                side=order.side,
                status="FAILED",
                error_message=f"No next-open price for {order.ticker}",
            )

        if order.side == "BUY":
            cost = order.quantity * fill_price
            if cost > self._cash:
                return OrderStatus(
                    broker_order_id=order_id,
                    ticker=order.ticker,
                    side=order.side,
                    status="FAILED",
                    error_message="Insufficient cash",
                )
            self._cash -= cost
            self._add_position(order.ticker, order.quantity, fill_price)
        elif order.side == "SELL":
            self._reduce_position(order.ticker, order.quantity)
            self._cash += order.quantity * fill_price

        status = OrderStatus(
            broker_order_id=order_id,
            ticker=order.ticker,
            side=order.side,
            status="FILLED",
            filled_quantity=order.quantity,
            filled_price=fill_price,
            filled_at=datetime.now(tz=timezone.utc),
        )
        self._orders[order_id] = status
        return status

    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        """Return stored order status."""
        status = self._orders.get(broker_order_id)
        if status is None:
            return OrderStatus(
                broker_order_id=broker_order_id,
                ticker="",
                side="",
                status="FAILED",
                error_message="Order not found",
            )
        return status

    async def get_positions(self) -> list[BrokerPosition]:
        """Return all tracked positions with current prices from next-open."""
        positions = []
        for ticker, pos in self._positions.items():
            qty = pos["quantity"]
            if qty <= 0:
                continue
            current = self._next_open_prices.get(ticker, pos["avg_price"])
            positions.append(
                BrokerPosition(
                    ticker=ticker,
                    quantity=qty,
                    avg_price=pos["avg_price"],
                    current_price=current,
                    unrealized_pnl=(current - pos["avg_price"]) * qty,
                )
            )
        return positions

    async def get_instruments(
        self, *, search: str | None = None
    ) -> list[BrokerInstrument]:
        """Return empty instrument list (simulated)."""
        return []

    def get_portfolio_value(self) -> Decimal:
        """Compute total portfolio value (cash + positions at current prices)."""
        total = self._cash
        for ticker, pos in self._positions.items():
            qty = pos["quantity"]
            if qty <= 0:
                continue
            price = self._next_open_prices.get(ticker, pos["avg_price"])
            total += qty * price
        return total

    @property
    def cash(self) -> Decimal:
        return self._cash

    def reset(self) -> None:
        """Clear all state and reset to initial capital."""
        self._cash = self._initial_capital
        self._positions.clear()
        self._next_open_prices.clear()
        self._orders.clear()

    # ── Private helpers ──────────────────────────────────────────────

    def _add_position(
        self, ticker: str, quantity: Decimal, price: Decimal
    ) -> None:
        if ticker in self._positions:
            existing = self._positions[ticker]
            total_qty = existing["quantity"] + quantity
            total_cost = existing["quantity"] * existing["avg_price"] + quantity * price
            existing["avg_price"] = (total_cost / total_qty).quantize(Decimal("0.0001"))
            existing["quantity"] = total_qty
        else:
            self._positions[ticker] = {
                "quantity": quantity,
                "avg_price": price,
            }

    def _reduce_position(self, ticker: str, quantity: Decimal) -> None:
        if ticker in self._positions:
            self._positions[ticker]["quantity"] -= quantity
            if self._positions[ticker]["quantity"] <= 0:
                del self._positions[ticker]
