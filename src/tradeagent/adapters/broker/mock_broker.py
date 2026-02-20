"""Mock broker adapter — in-memory broker for testing and development."""

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


class MockBrokerAdapter(BrokerAdapter):
    """In-memory broker that immediately fills orders. For testing only."""

    def __init__(self) -> None:
        self._positions: dict[str, dict] = {}  # ticker -> {quantity, avg_price}
        self._current_prices: dict[str, Decimal] = {}
        self._orders: dict[str, OrderStatus] = {}

    async def place_order(self, order: OrderRequest) -> OrderStatus:
        """Immediately fill the order and update in-memory positions."""
        order_id = str(uuid4())
        price = self._current_prices.get(order.ticker, Decimal("100.00"))

        # Update position tracking
        if order.side == "BUY":
            self._add_position(order.ticker, order.quantity, price)
        elif order.side == "SELL":
            self._reduce_position(order.ticker, order.quantity)

        status = OrderStatus(
            broker_order_id=order_id,
            ticker=order.ticker,
            side=order.side,
            status="FILLED",
            filled_quantity=order.quantity,
            filled_price=price,
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
        """Return all tracked positions."""
        positions = []
        for ticker, pos in self._positions.items():
            qty = pos["quantity"]
            if qty <= 0:
                continue
            current = self._current_prices.get(ticker, pos["avg_price"])
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
        """Return empty instrument list (mock)."""
        return []

    # ── Test helpers ─────────────────────────────────────────────────

    def set_current_price(self, ticker: str, price: Decimal) -> None:
        """Set the current price for a ticker (for testing)."""
        self._current_prices[ticker] = price

    def reset(self) -> None:
        """Clear all positions and orders."""
        self._positions.clear()
        self._current_prices.clear()
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
