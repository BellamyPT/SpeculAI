from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from tradeagent.core.exceptions import RepositoryError
from tradeagent.models.stock import Stock
from tradeagent.models.trade import Trade


class TradeRepository:
    """Data access layer for Trade."""

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        stock_id: int,
        side: str,
        quantity: object,
        price: object,
        total_value: object,
        currency: str,
        status: str,
        decision_report_id: int | None = None,
        broker_order_id: str | None = None,
        executed_at: datetime | None = None,
        is_backtest: bool = False,
        backtest_run_id: object | None = None,
    ) -> Trade:
        try:
            trade = Trade(
                stock_id=stock_id,
                side=side,
                quantity=quantity,
                price=price,
                total_value=total_value,
                currency=currency,
                status=status,
                decision_report_id=decision_report_id,
                broker_order_id=broker_order_id,
                executed_at=executed_at,
                is_backtest=is_backtest,
                backtest_run_id=backtest_run_id,
            )
            session.add(trade)
            await session.flush()
            return trade
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to create trade") from exc

    @staticmethod
    async def get_by_id(session: AsyncSession, trade_id: int) -> Trade | None:
        try:
            return await session.get(Trade, trade_id)
        except SQLAlchemyError as exc:
            raise RepositoryError(f"Failed to get trade {trade_id}") from exc

    @staticmethod
    async def update_status(
        session: AsyncSession,
        trade_id: int,
        status: str,
        *,
        executed_at: datetime | None = None,
        broker_order_id: str | None = None,
    ) -> Trade:
        try:
            trade = await session.get(Trade, trade_id)
            if trade is None:
                raise RepositoryError(f"Trade {trade_id} not found")
            trade.status = status
            if executed_at is not None:
                trade.executed_at = executed_at
            if broker_order_id is not None:
                trade.broker_order_id = broker_order_id
            await session.flush()
            return trade
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to update trade status {trade_id}"
            ) from exc

    @staticmethod
    async def get_history(
        session: AsyncSession,
        *,
        ticker: str | None = None,
        side: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        include_backtest: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Trade], int]:
        """Get filtered, paginated trade history."""
        try:
            filters = TradeRepository._build_history_filters(
                ticker=ticker,
                side=side,
                start_date=start_date,
                end_date=end_date,
                include_backtest=include_backtest,
            )

            base = select(Trade).join(Trade.stock)
            for f in filters:
                base = base.where(f)

            count_q = select(func.count()).select_from(base.subquery())
            total = (await session.execute(count_q)).scalar_one()

            data_q = (
                base.options(joinedload(Trade.stock))
                .order_by(Trade.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = (await session.execute(data_q)).unique().scalars().all()
            return list(rows), total
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to get trade history") from exc

    @staticmethod
    async def get_trades_by_decision(
        session: AsyncSession, decision_report_id: int
    ) -> list[Trade]:
        try:
            result = await session.execute(
                select(Trade)
                .where(Trade.decision_report_id == decision_report_id)
                .order_by(Trade.created_at)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get trades for decision {decision_report_id}"
            ) from exc

    @staticmethod
    async def get_trades_by_stock(
        session: AsyncSession,
        stock_id: int,
        *,
        include_backtest: bool = False,
        limit: int | None = None,
    ) -> list[Trade]:
        try:
            q = select(Trade).where(Trade.stock_id == stock_id)
            if not include_backtest:
                q = q.where(Trade.is_backtest.is_(False))
            q = q.order_by(Trade.created_at.desc())
            if limit is not None:
                q = q.limit(limit)
            result = await session.execute(q)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get trades for stock {stock_id}"
            ) from exc

    # ── Private helpers ─────────────────────────────────────────────

    @staticmethod
    def _build_history_filters(
        *,
        ticker: str | None,
        side: str | None,
        start_date: date | None,
        end_date: date | None,
        include_backtest: bool,
    ) -> list:
        """Build a list of WHERE clause conditions for trade history."""
        filters = []
        if not include_backtest:
            filters.append(Trade.is_backtest.is_(False))
        if ticker is not None:
            filters.append(Stock.ticker == ticker)
        if side is not None:
            filters.append(Trade.side == side)
        if start_date is not None:
            filters.append(Trade.created_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date is not None:
            filters.append(Trade.created_at <= datetime.combine(end_date, datetime.max.time()))
        return filters
