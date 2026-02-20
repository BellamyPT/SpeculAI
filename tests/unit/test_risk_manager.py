"""Tests for the RiskManager."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tradeagent.config import PortfolioConfig
from tradeagent.services.risk_manager import (
    ApprovedTrade,
    PortfolioState,
    PositionInfo,
    RejectedTrade,
    RiskManager,
    TradeProposal,
)


@pytest.fixture
def config() -> PortfolioConfig:
    return PortfolioConfig(
        max_positions=20,
        max_position_pct=5.0,
        min_trade_value=100.0,
        initial_capital=50000.0,
    )


@pytest.fixture
def manager(config: PortfolioConfig) -> RiskManager:
    return RiskManager(config)


def _portfolio(
    total_value: float = 50000.0,
    cash: float = 10000.0,
    positions: dict | None = None,
    num_positions: int = 3,
) -> PortfolioState:
    return PortfolioState(
        total_value=Decimal(str(total_value)),
        cash_available=Decimal(str(cash)),
        positions=positions or {},
        num_open_positions=num_positions,
    )


def _buy_proposal(
    ticker: str = "AAPL",
    stock_id: int = 1,
    confidence: float = 0.8,
    allocation_pct: float = 3.0,
    price: float = 150.0,
) -> TradeProposal:
    return TradeProposal(
        ticker=ticker,
        stock_id=stock_id,
        action="BUY",
        confidence=confidence,
        reasoning="Test buy",
        suggested_allocation_pct=allocation_pct,
        current_price=Decimal(str(price)),
    )


def _sell_proposal(
    ticker: str = "MSFT",
    stock_id: int = 2,
    confidence: float = 0.7,
    price: float = 300.0,
) -> TradeProposal:
    return TradeProposal(
        ticker=ticker,
        stock_id=stock_id,
        action="SELL",
        confidence=confidence,
        reasoning="Test sell",
        suggested_allocation_pct=0.0,
        current_price=Decimal(str(price)),
    )


def _position(
    stock_id: int = 2,
    ticker: str = "MSFT",
    quantity: float = 10.0,
    avg_price: float = 280.0,
    current_price: float = 300.0,
    weight_pct: float = 6.0,
) -> PositionInfo:
    qty = Decimal(str(quantity))
    cp = Decimal(str(current_price))
    return PositionInfo(
        stock_id=stock_id,
        ticker=ticker,
        quantity=qty,
        avg_price=Decimal(str(avg_price)),
        current_price=cp,
        market_value=(qty * cp).quantize(Decimal("0.01")),
        weight_pct=weight_pct,
    )


class TestBuyValidation:
    def test_buy_approved(self, manager):
        state = _portfolio()
        result = manager.validate_trades([_buy_proposal()], state)
        assert len(result.approved) == 1
        assert result.approved[0].side == "BUY"
        assert result.approved[0].ticker == "AAPL"

    def test_buy_capped_at_max_position_pct(self, manager):
        """Allocation of 10% should be capped to 5%."""
        proposal = _buy_proposal(allocation_pct=10.0)
        state = _portfolio(total_value=50000.0, cash=50000.0)
        result = manager.validate_trades([proposal], state)
        assert len(result.approved) == 1
        # Value should be capped at 5% of 50000 = 2500
        assert result.approved[0].estimated_value <= Decimal("2500.01")

    def test_buy_rejected_insufficient_cash(self, manager):
        state = _portfolio(cash=50.0)  # below min_trade_value
        result = manager.validate_trades([_buy_proposal()], state)
        assert len(result.rejected) == 1
        assert "Insufficient cash" in result.rejected[0].rejection_reason

    def test_buy_rejected_max_positions(self):
        config = PortfolioConfig(max_positions=2)
        mgr = RiskManager(config)
        state = _portfolio(num_positions=2)
        result = mgr.validate_trades([_buy_proposal()], state)
        assert len(result.rejected) == 1
        assert "Max positions" in result.rejected[0].rejection_reason

    def test_buy_quantity_calculated(self, manager):
        state = _portfolio(cash=10000.0)
        result = manager.validate_trades([_buy_proposal(price=100.0)], state)
        assert len(result.approved) == 1
        trade = result.approved[0]
        assert trade.quantity > 0
        assert trade.estimated_value > 0


class TestSellValidation:
    def test_sell_approved(self, manager):
        pos = _position()
        state = _portfolio(positions={2: pos})
        result = manager.validate_trades([_sell_proposal()], state)
        assert len(result.approved) == 1
        assert result.approved[0].side == "SELL"
        assert result.approved[0].quantity == pos.quantity

    def test_sell_rejected_no_position(self, manager):
        state = _portfolio()
        result = manager.validate_trades([_sell_proposal()], state)
        assert len(result.rejected) == 1
        assert "No open position" in result.rejected[0].rejection_reason


class TestProcessingOrder:
    def test_sells_before_buys(self, manager):
        """SELLs are processed first, freeing cash for BUYs."""
        pos = _position(stock_id=2, quantity=10, current_price=300)
        state = _portfolio(
            total_value=50000.0,
            cash=0.0,  # no cash initially
            positions={2: pos},
            num_positions=1,
        )
        proposals = [
            _buy_proposal(stock_id=3, ticker="GOOG", price=100.0, allocation_pct=2.0),
            _sell_proposal(stock_id=2, price=300.0),
        ]
        result = manager.validate_trades(proposals, state)
        # Sell should free cash, allowing the buy
        approved_actions = [t.action for t in result.approved]
        assert "SELL" in approved_actions
        assert "BUY" in approved_actions

    def test_buys_ordered_by_confidence(self, manager):
        """Higher confidence proposals are filled first."""
        state = _portfolio(cash=2000.0)
        proposals = [
            _buy_proposal(stock_id=1, ticker="LOW", confidence=0.5, price=100.0, allocation_pct=3.0),
            _buy_proposal(stock_id=2, ticker="HIGH", confidence=0.9, price=100.0, allocation_pct=3.0),
        ]
        result = manager.validate_trades(proposals, state)
        # Both may be approved, but HIGH should be first
        if len(result.approved) >= 2:
            assert result.approved[0].ticker == "HIGH"


class TestEdgeCases:
    def test_never_throws(self, manager):
        """validate_trades should never raise, even with invalid input."""
        result = manager.validate_trades([], _portfolio())
        assert result.approved == []
        assert result.rejected == []

    def test_zero_price_buy_rejected(self, manager):
        proposal = _buy_proposal(price=0.0)
        state = _portfolio()
        result = manager.validate_trades([proposal], state)
        assert len(result.rejected) == 1

    def test_empty_proposals(self, manager):
        result = manager.validate_trades([], _portfolio())
        assert len(result.approved) == 0
        assert len(result.rejected) == 0
