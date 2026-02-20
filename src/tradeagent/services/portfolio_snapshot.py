"""Portfolio snapshot service — creates daily snapshots of portfolio state."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from tradeagent.config import Settings
from tradeagent.core.logging import get_logger
from tradeagent.models.portfolio import PortfolioSnapshot
from tradeagent.repositories.portfolio import PortfolioRepository
from tradeagent.repositories.stock import StockRepository

log = get_logger(__name__)


class PortfolioSnapshotService:
    """Create daily snapshots of portfolio value and position breakdown."""

    @staticmethod
    async def create_daily_snapshot(
        session: AsyncSession,
        settings: Settings,
    ) -> PortfolioSnapshot:
        """Compute current portfolio state and persist a snapshot.

        Computes:
        - total_value = cash + sum(position market values)
        - daily_pnl = total_value - previous snapshot total_value
        - cumulative_pnl_pct = (total_value - initial_capital) / initial_capital * 100
        """
        initial_capital = Decimal(str(settings.portfolio.initial_capital))
        positions = await PortfolioRepository.get_open_positions(session)

        invested = Decimal("0")
        position_snapshots_data: list[dict] = []

        for pos in positions:
            latest_price = await StockRepository.get_latest_price(session, pos.stock_id)
            if latest_price is None:
                current_price = pos.avg_price
            else:
                current_price = latest_price.close

            market_value = (pos.quantity * current_price).quantize(Decimal("0.0001"))
            cost_basis = (pos.quantity * pos.avg_price).quantize(Decimal("0.0001"))
            unrealized_pnl = market_value - cost_basis
            invested += market_value

            position_snapshots_data.append({
                "stock_id": pos.stock_id,
                "quantity": pos.quantity,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "weight_pct": Decimal("0"),  # computed after total is known
            })

        # Cash = initial_capital - total cost basis of open positions
        total_cost_basis = sum(
            (p.quantity * p.avg_price).quantize(Decimal("0.0001"))
            for p in positions
        )
        cash = initial_capital - total_cost_basis
        total_value = cash + invested

        # Compute weights
        for snap_data in position_snapshots_data:
            if total_value > 0:
                snap_data["weight_pct"] = (
                    snap_data["market_value"] / total_value * 100
                ).quantize(Decimal("0.001"))

        # Daily P&L
        previous_snapshot = await PortfolioRepository.get_latest_snapshot(session)
        if previous_snapshot is not None:
            daily_pnl = total_value - previous_snapshot.total_value
        else:
            daily_pnl = total_value - initial_capital

        # Cumulative P&L %
        if initial_capital > 0:
            cumulative_pnl_pct = (
                (total_value - initial_capital) / initial_capital * 100
            ).quantize(Decimal("0.0001"))
        else:
            cumulative_pnl_pct = Decimal("0")

        snapshot = await PortfolioRepository.create_snapshot(
            session,
            date=date.today(),
            total_value=total_value,
            cash=cash,
            invested=invested,
            daily_pnl=daily_pnl.quantize(Decimal("0.0001")),
            cumulative_pnl_pct=cumulative_pnl_pct,
            num_positions=len(positions),
        )

        # Create position snapshots
        for snap_data in position_snapshots_data:
            snap_data["portfolio_snapshot_id"] = snapshot.id

        await PortfolioRepository.bulk_create_position_snapshots(
            session, position_snapshots_data
        )

        await session.commit()

        log.info(
            "portfolio_snapshot_created",
            date=str(date.today()),
            total_value=str(total_value),
            num_positions=len(positions),
        )
        return snapshot
