"""Risk manager — validates trade proposals against portfolio constraints."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from tradeagent.config import PortfolioConfig
from tradeagent.core.logging import get_logger

log = get_logger(__name__)


# ── DTOs ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TradeProposal:
    """LLM-generated trade recommendation before risk validation."""

    ticker: str
    stock_id: int
    action: str  # "BUY" or "SELL"
    confidence: float
    reasoning: str
    suggested_allocation_pct: float
    current_price: Decimal
    currency: str = "USD"


@dataclass(frozen=True, slots=True)
class ApprovedTrade:
    """A trade that passed risk validation."""

    ticker: str
    stock_id: int
    action: str
    side: str  # "BUY" or "SELL"
    quantity: Decimal
    estimated_value: Decimal
    confidence: float
    reasoning: str


@dataclass(frozen=True, slots=True)
class RejectedTrade:
    """A trade rejected by risk validation."""

    ticker: str
    stock_id: int
    action: str
    confidence: float
    rejection_reason: str


@dataclass
class RiskValidationResult:
    """Combined result of risk validation."""

    approved: list[ApprovedTrade] = field(default_factory=list)
    rejected: list[RejectedTrade] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PositionInfo:
    """Current position information used by the risk manager."""

    stock_id: int
    ticker: str
    quantity: Decimal
    avg_price: Decimal
    current_price: Decimal
    market_value: Decimal
    weight_pct: float


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """Snapshot of portfolio state for risk validation."""

    total_value: Decimal
    cash_available: Decimal
    positions: dict[int, PositionInfo]  # keyed by stock_id
    num_open_positions: int


# ── Risk Manager ─────────────────────────────────────────────────────


class RiskManager:
    """Validate trade proposals against portfolio constraints.

    Algorithm: process SELLs first (free cash + slots), then BUYs by
    confidence descending. Never raises — all errors are caught and
    proposals are rejected with a reason.
    """

    def __init__(self, config: PortfolioConfig) -> None:
        self._cfg = config

    def validate_trades(
        self,
        proposals: list[TradeProposal],
        portfolio_state: PortfolioState,
    ) -> RiskValidationResult:
        """Validate all proposals. Never throws."""
        result = RiskValidationResult()
        try:
            sells = [p for p in proposals if p.action == "SELL"]
            buys = [p for p in proposals if p.action == "BUY"]

            cash_freed = self._process_sells(sells, portfolio_state, result)

            available_cash = portfolio_state.cash_available + cash_freed
            available_slots = self._cfg.max_positions - (
                portfolio_state.num_open_positions - len(result.approved)
            )
            self._process_buys(
                buys, portfolio_state, available_cash, available_slots, result
            )
        except Exception:
            log.error("risk_validation_unexpected_error", exc_info=True)

        return result

    # ── Sell processing ──────────────────────────────────────────────

    def _process_sells(
        self,
        sell_proposals: list[TradeProposal],
        portfolio_state: PortfolioState,
        result: RiskValidationResult,
    ) -> Decimal:
        """Validate sell proposals. Returns total cash freed."""
        cash_freed = Decimal("0")

        for proposal in sell_proposals:
            position = portfolio_state.positions.get(proposal.stock_id)
            if position is None:
                result.rejected.append(
                    RejectedTrade(
                        ticker=proposal.ticker,
                        stock_id=proposal.stock_id,
                        action=proposal.action,
                        confidence=proposal.confidence,
                        rejection_reason="No open position to sell",
                    )
                )
                continue

            quantity, value = self._calculate_sell_quantity(proposal, position)
            result.approved.append(
                ApprovedTrade(
                    ticker=proposal.ticker,
                    stock_id=proposal.stock_id,
                    action=proposal.action,
                    side="SELL",
                    quantity=quantity,
                    estimated_value=value,
                    confidence=proposal.confidence,
                    reasoning=proposal.reasoning,
                )
            )
            cash_freed += value

        return cash_freed

    # ── Buy processing ───────────────────────────────────────────────

    def _process_buys(
        self,
        buy_proposals: list[TradeProposal],
        portfolio_state: PortfolioState,
        available_cash: Decimal,
        available_slots: int,
        result: RiskValidationResult,
    ) -> None:
        """Validate buy proposals sorted by confidence descending."""
        sorted_buys = sorted(buy_proposals, key=lambda p: p.confidence, reverse=True)

        for proposal in sorted_buys:
            # Check slot availability
            if available_slots <= 0:
                result.rejected.append(
                    RejectedTrade(
                        ticker=proposal.ticker,
                        stock_id=proposal.stock_id,
                        action=proposal.action,
                        confidence=proposal.confidence,
                        rejection_reason=f"Max positions ({self._cfg.max_positions}) reached",
                    )
                )
                continue

            calc = self._calculate_buy_quantity(
                proposal, portfolio_state.total_value, available_cash
            )
            if calc is None:
                result.rejected.append(
                    RejectedTrade(
                        ticker=proposal.ticker,
                        stock_id=proposal.stock_id,
                        action=proposal.action,
                        confidence=proposal.confidence,
                        rejection_reason="Insufficient cash or below min trade value",
                    )
                )
                continue

            quantity, value = calc
            result.approved.append(
                ApprovedTrade(
                    ticker=proposal.ticker,
                    stock_id=proposal.stock_id,
                    action=proposal.action,
                    side="BUY",
                    quantity=quantity,
                    estimated_value=value,
                    confidence=proposal.confidence,
                    reasoning=proposal.reasoning,
                )
            )
            available_cash -= value
            available_slots -= 1

    # ── Quantity calculations ────────────────────────────────────────

    def _calculate_buy_quantity(
        self,
        proposal: TradeProposal,
        portfolio_total_value: Decimal,
        available_cash: Decimal,
    ) -> tuple[Decimal, Decimal] | None:
        """Calculate buy quantity respecting position size and cash limits.

        Returns (quantity, estimated_value) or None if trade is not viable.
        """
        if proposal.current_price <= 0:
            return None

        # Max allocation = max_position_pct of total portfolio
        max_value = portfolio_total_value * Decimal(str(self._cfg.max_position_pct / 100))

        # Requested allocation
        requested_value = portfolio_total_value * Decimal(
            str(proposal.suggested_allocation_pct / 100)
        )

        # Cap at max position size and available cash
        trade_value = min(requested_value, max_value, available_cash)

        # Check min trade value
        min_val = Decimal(str(self._cfg.min_trade_value))
        if trade_value < min_val:
            return None

        quantity = (trade_value / proposal.current_price).quantize(Decimal("0.000001"))
        if quantity <= 0:
            return None

        estimated_value = (quantity * proposal.current_price).quantize(Decimal("0.01"))
        return quantity, estimated_value

    def _calculate_sell_quantity(
        self,
        proposal: TradeProposal,
        position: PositionInfo,
    ) -> tuple[Decimal, Decimal]:
        """Calculate sell quantity — sells the entire position."""
        quantity = position.quantity
        value = (quantity * proposal.current_price).quantize(Decimal("0.01"))
        return quantity, value
