from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from tradeagent.core.exceptions import RepositoryError
from tradeagent.models.stock import Stock, StockFundamental, StockPrice


class StockRepository:
    """Data access layer for Stock, StockPrice, and StockFundamental."""

    @staticmethod
    async def get_by_id(session: AsyncSession, stock_id: int) -> Stock | None:
        try:
            return await session.get(Stock, stock_id)
        except SQLAlchemyError as exc:
            raise RepositoryError(f"Failed to get stock {stock_id}") from exc

    @staticmethod
    async def get_by_ticker(session: AsyncSession, ticker: str) -> Stock | None:
        try:
            result = await session.execute(
                select(Stock).where(Stock.ticker == ticker)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"Failed to get stock by ticker {ticker}") from exc

    @staticmethod
    async def get_all_active(
        session: AsyncSession, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[Stock], int]:
        try:
            base = select(Stock).where(Stock.is_active.is_(True))
            count_q = select(func.count()).select_from(base.subquery())
            total = (await session.execute(count_q)).scalar_one()

            data_q = base.order_by(Stock.ticker).limit(limit).offset(offset)
            rows = (await session.execute(data_q)).scalars().all()
            return list(rows), total
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to list active stocks") from exc

    @staticmethod
    async def get_by_sector(
        session: AsyncSession,
        sector: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Stock], int]:
        try:
            base = select(Stock).where(
                Stock.sector == sector, Stock.is_active.is_(True)
            )
            count_q = select(func.count()).select_from(base.subquery())
            total = (await session.execute(count_q)).scalar_one()

            data_q = base.order_by(Stock.ticker).limit(limit).offset(offset)
            rows = (await session.execute(data_q)).scalars().all()
            return list(rows), total
        except SQLAlchemyError as exc:
            raise RepositoryError(f"Failed to list stocks in sector {sector}") from exc

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        ticker: str,
        name: str,
        exchange: str,
        currency: str,
        sector: str | None = None,
        industry: str | None = None,
        country: str | None = None,
        is_active: bool = True,
    ) -> Stock:
        try:
            stock = Stock(
                ticker=ticker,
                name=name,
                exchange=exchange,
                currency=currency,
                sector=sector,
                industry=industry,
                country=country,
                is_active=is_active,
            )
            session.add(stock)
            await session.flush()
            return stock
        except SQLAlchemyError as exc:
            raise RepositoryError(f"Failed to create stock {ticker}") from exc

    @staticmethod
    async def update(
        session: AsyncSession, stock_id: int, **kwargs: object
    ) -> Stock:
        try:
            stock = await session.get(Stock, stock_id)
            if stock is None:
                raise RepositoryError(f"Stock {stock_id} not found")
            for key, value in kwargs.items():
                setattr(stock, key, value)
            await session.flush()
            return stock
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            raise RepositoryError(f"Failed to update stock {stock_id}") from exc

    @staticmethod
    async def deactivate(session: AsyncSession, stock_id: int) -> None:
        try:
            stock = await session.get(Stock, stock_id)
            if stock is None:
                raise RepositoryError(f"Stock {stock_id} not found")
            stock.is_active = False
            await session.flush()
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            raise RepositoryError(f"Failed to deactivate stock {stock_id}") from exc

    # ── StockPrice queries ──────────────────────────────────────────

    @staticmethod
    async def get_prices(
        session: AsyncSession,
        stock_id: int,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[StockPrice], int]:
        try:
            base = select(StockPrice).where(StockPrice.stock_id == stock_id)
            if start_date is not None:
                base = base.where(StockPrice.date >= start_date)
            if end_date is not None:
                base = base.where(StockPrice.date <= end_date)

            count_q = select(func.count()).select_from(base.subquery())
            total = (await session.execute(count_q)).scalar_one()

            data_q = (
                base.order_by(StockPrice.date.desc()).limit(limit).offset(offset)
            )
            rows = (await session.execute(data_q)).scalars().all()
            return list(rows), total
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get prices for stock {stock_id}"
            ) from exc

    @staticmethod
    async def get_latest_price(
        session: AsyncSession, stock_id: int
    ) -> StockPrice | None:
        try:
            result = await session.execute(
                select(StockPrice)
                .where(StockPrice.stock_id == stock_id)
                .order_by(StockPrice.date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get latest price for stock {stock_id}"
            ) from exc

    @staticmethod
    async def bulk_upsert_prices(
        session: AsyncSession, prices: list[dict]
    ) -> int:
        """Insert or update stock prices. Returns the number of rows affected.

        Each dict must contain: stock_id, date, open, high, low, close, adj_close, volume.
        Conflict target: (stock_id, date).
        """
        if not prices:
            return 0
        try:
            stmt = pg_insert(StockPrice).values(prices)
            stmt = stmt.on_conflict_do_update(
                index_elements=["stock_id", "date"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "adj_close": stmt.excluded.adj_close,
                    "volume": stmt.excluded.volume,
                },
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.rowcount
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to bulk upsert stock prices") from exc

    # ── StockFundamental queries ────────────────────────────────────

    @staticmethod
    async def upsert_fundamental(
        session: AsyncSession,
        *,
        stock_id: int,
        snapshot_date: date,
        **kwargs: object,
    ) -> StockFundamental:
        """Insert or update a fundamental snapshot for a stock."""
        try:
            values = {"stock_id": stock_id, "snapshot_date": snapshot_date, **kwargs}
            stmt = pg_insert(StockFundamental).values(values)
            update_cols = {k: getattr(stmt.excluded, k) for k in kwargs}
            stmt = stmt.on_conflict_do_update(
                index_elements=["stock_id", "snapshot_date"],
                set_=update_cols,
            )
            await session.execute(stmt)
            await session.flush()

            # Return the row — populate_existing overwrites identity-map cache
            result = await session.execute(
                select(StockFundamental)
                .where(
                    StockFundamental.stock_id == stock_id,
                    StockFundamental.snapshot_date == snapshot_date,
                )
                .execution_options(populate_existing=True)
            )
            return result.scalar_one()
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to upsert fundamental for stock {stock_id}"
            ) from exc

    @staticmethod
    async def get_latest_fundamental(
        session: AsyncSession, stock_id: int
    ) -> StockFundamental | None:
        try:
            result = await session.execute(
                select(StockFundamental)
                .where(StockFundamental.stock_id == stock_id)
                .order_by(StockFundamental.snapshot_date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get latest fundamental for stock {stock_id}"
            ) from exc
