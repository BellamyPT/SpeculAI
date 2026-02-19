from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from tradeagent.core.exceptions import RepositoryError
from tradeagent.core.types import PositionStatus
from tradeagent.models.portfolio import PortfolioSnapshot, Position, PositionSnapshot


class PortfolioRepository:
    """Data access layer for Position, PortfolioSnapshot, and PositionSnapshot."""

    # ── Position management ─────────────────────────────────────────

    @staticmethod
    async def get_open_positions(session: AsyncSession) -> list[Position]:
        try:
            result = await session.execute(
                select(Position)
                .where(Position.status == PositionStatus.OPEN)
                .order_by(Position.opened_at)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to get open positions") from exc

    @staticmethod
    async def get_open_position_by_stock(
        session: AsyncSession, stock_id: int
    ) -> Position | None:
        try:
            result = await session.execute(
                select(Position).where(
                    Position.stock_id == stock_id,
                    Position.status == PositionStatus.OPEN,
                )
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get open position for stock {stock_id}"
            ) from exc

    @staticmethod
    async def get_position_by_id(
        session: AsyncSession, position_id: int
    ) -> Position | None:
        try:
            return await session.get(Position, position_id)
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get position {position_id}"
            ) from exc

    @staticmethod
    async def create_position(
        session: AsyncSession,
        *,
        stock_id: int,
        quantity: object,
        avg_price: object,
        currency: str,
        opened_at: datetime,
    ) -> Position:
        try:
            position = Position(
                stock_id=stock_id,
                quantity=quantity,
                avg_price=avg_price,
                currency=currency,
                opened_at=opened_at,
                status=PositionStatus.OPEN,
            )
            session.add(position)
            await session.flush()
            return position
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to create position for stock {stock_id}"
            ) from exc

    @staticmethod
    async def update_position(
        session: AsyncSession, position_id: int, **kwargs: object
    ) -> Position:
        try:
            position = await session.get(Position, position_id)
            if position is None:
                raise RepositoryError(f"Position {position_id} not found")
            for key, value in kwargs.items():
                setattr(position, key, value)
            await session.flush()
            return position
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to update position {position_id}"
            ) from exc

    @staticmethod
    async def close_position(
        session: AsyncSession, position_id: int, closed_at: datetime
    ) -> Position:
        try:
            position = await session.get(Position, position_id)
            if position is None:
                raise RepositoryError(f"Position {position_id} not found")
            position.status = PositionStatus.CLOSED
            position.closed_at = closed_at
            await session.flush()
            return position
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to close position {position_id}"
            ) from exc

    @staticmethod
    async def get_positions_history(
        session: AsyncSession,
        *,
        include_closed: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Position], int]:
        try:
            base = select(Position)
            if not include_closed:
                base = base.where(Position.status == PositionStatus.OPEN)

            count_q = select(func.count()).select_from(base.subquery())
            total = (await session.execute(count_q)).scalar_one()

            data_q = (
                base.order_by(Position.opened_at.desc()).limit(limit).offset(offset)
            )
            rows = (await session.execute(data_q)).scalars().all()
            return list(rows), total
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to get positions history") from exc

    # ── PortfolioSnapshot queries ───────────────────────────────────

    @staticmethod
    async def create_snapshot(
        session: AsyncSession,
        *,
        date: date,
        total_value: object,
        cash: object,
        invested: object,
        daily_pnl: object,
        cumulative_pnl_pct: object,
        num_positions: int,
        is_backtest: bool = False,
        backtest_run_id: object | None = None,
    ) -> PortfolioSnapshot:
        try:
            snapshot = PortfolioSnapshot(
                date=date,
                total_value=total_value,
                cash=cash,
                invested=invested,
                daily_pnl=daily_pnl,
                cumulative_pnl_pct=cumulative_pnl_pct,
                num_positions=num_positions,
                is_backtest=is_backtest,
                backtest_run_id=backtest_run_id,
            )
            session.add(snapshot)
            await session.flush()
            return snapshot
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to create portfolio snapshot") from exc

    @staticmethod
    async def get_latest_snapshot(
        session: AsyncSession, *, is_backtest: bool = False
    ) -> PortfolioSnapshot | None:
        try:
            result = await session.execute(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.is_backtest == is_backtest)
                .order_by(PortfolioSnapshot.date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to get latest portfolio snapshot") from exc

    @staticmethod
    async def get_snapshots(
        session: AsyncSession,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        is_backtest: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PortfolioSnapshot], int]:
        try:
            base = select(PortfolioSnapshot).where(
                PortfolioSnapshot.is_backtest == is_backtest
            )
            if start_date is not None:
                base = base.where(PortfolioSnapshot.date >= start_date)
            if end_date is not None:
                base = base.where(PortfolioSnapshot.date <= end_date)

            count_q = select(func.count()).select_from(base.subquery())
            total = (await session.execute(count_q)).scalar_one()

            data_q = (
                base.order_by(PortfolioSnapshot.date.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = (await session.execute(data_q)).scalars().all()
            return list(rows), total
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to get portfolio snapshots") from exc

    # ── PositionSnapshot queries ────────────────────────────────────

    @staticmethod
    async def create_position_snapshot(
        session: AsyncSession,
        *,
        portfolio_snapshot_id: int,
        stock_id: int,
        quantity: object,
        market_value: object,
        unrealized_pnl: object,
        weight_pct: object,
    ) -> PositionSnapshot:
        try:
            snap = PositionSnapshot(
                portfolio_snapshot_id=portfolio_snapshot_id,
                stock_id=stock_id,
                quantity=quantity,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                weight_pct=weight_pct,
            )
            session.add(snap)
            await session.flush()
            return snap
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to create position snapshot") from exc

    @staticmethod
    async def bulk_create_position_snapshots(
        session: AsyncSession, snapshots: list[dict]
    ) -> list[PositionSnapshot]:
        if not snapshots:
            return []
        try:
            objects = [PositionSnapshot(**s) for s in snapshots]
            session.add_all(objects)
            await session.flush()
            return objects
        except SQLAlchemyError as exc:
            raise RepositoryError(
                "Failed to bulk create position snapshots"
            ) from exc

    @staticmethod
    async def get_position_snapshots_for_portfolio(
        session: AsyncSession, portfolio_snapshot_id: int
    ) -> list[PositionSnapshot]:
        try:
            result = await session.execute(
                select(PositionSnapshot).where(
                    PositionSnapshot.portfolio_snapshot_id == portfolio_snapshot_id
                )
            )
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get position snapshots for portfolio {portfolio_snapshot_id}"
            ) from exc
