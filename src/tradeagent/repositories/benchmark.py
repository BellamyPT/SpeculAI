from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from tradeagent.core.exceptions import RepositoryError
from tradeagent.models.benchmark import Benchmark, BenchmarkPrice


class BenchmarkRepository:
    """Data access layer for Benchmark and BenchmarkPrice."""

    @staticmethod
    async def get_by_id(
        session: AsyncSession, benchmark_id: int
    ) -> Benchmark | None:
        try:
            return await session.get(Benchmark, benchmark_id)
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get benchmark {benchmark_id}"
            ) from exc

    @staticmethod
    async def get_by_symbol(
        session: AsyncSession, symbol: str
    ) -> Benchmark | None:
        try:
            result = await session.execute(
                select(Benchmark).where(Benchmark.symbol == symbol)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get benchmark by symbol {symbol}"
            ) from exc

    @staticmethod
    async def get_all(session: AsyncSession) -> list[Benchmark]:
        try:
            result = await session.execute(
                select(Benchmark).order_by(Benchmark.symbol)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to list benchmarks") from exc

    @staticmethod
    async def create(
        session: AsyncSession, *, symbol: str, name: str
    ) -> Benchmark:
        try:
            benchmark = Benchmark(symbol=symbol, name=name)
            session.add(benchmark)
            await session.flush()
            return benchmark
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to create benchmark {symbol}"
            ) from exc

    @staticmethod
    async def get_or_create(
        session: AsyncSession, *, symbol: str, name: str
    ) -> Benchmark:
        try:
            result = await session.execute(
                select(Benchmark).where(Benchmark.symbol == symbol)
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing
            benchmark = Benchmark(symbol=symbol, name=name)
            session.add(benchmark)
            await session.flush()
            return benchmark
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get_or_create benchmark {symbol}"
            ) from exc

    # ── BenchmarkPrice queries ──────────────────────────────────────

    @staticmethod
    async def get_prices(
        session: AsyncSession,
        benchmark_id: int,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[BenchmarkPrice], int]:
        try:
            base = select(BenchmarkPrice).where(
                BenchmarkPrice.benchmark_id == benchmark_id
            )
            if start_date is not None:
                base = base.where(BenchmarkPrice.date >= start_date)
            if end_date is not None:
                base = base.where(BenchmarkPrice.date <= end_date)

            count_q = select(func.count()).select_from(base.subquery())
            total = (await session.execute(count_q)).scalar_one()

            data_q = (
                base.order_by(BenchmarkPrice.date.desc()).limit(limit).offset(offset)
            )
            rows = (await session.execute(data_q)).scalars().all()
            return list(rows), total
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get prices for benchmark {benchmark_id}"
            ) from exc

    @staticmethod
    async def get_latest_price(
        session: AsyncSession, benchmark_id: int
    ) -> BenchmarkPrice | None:
        try:
            result = await session.execute(
                select(BenchmarkPrice)
                .where(BenchmarkPrice.benchmark_id == benchmark_id)
                .order_by(BenchmarkPrice.date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get latest price for benchmark {benchmark_id}"
            ) from exc

    @staticmethod
    async def bulk_upsert_prices(
        session: AsyncSession, prices: list[dict]
    ) -> int:
        """Insert or update benchmark prices. Returns the number of rows affected.

        Each dict must contain: benchmark_id, date, close.
        Conflict target: (benchmark_id, date).
        """
        if not prices:
            return 0
        try:
            stmt = pg_insert(BenchmarkPrice).values(prices)
            stmt = stmt.on_conflict_do_update(
                index_elements=["benchmark_id", "date"],
                set_={"close": stmt.excluded.close},
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.rowcount
        except SQLAlchemyError as exc:
            raise RepositoryError(
                "Failed to bulk upsert benchmark prices"
            ) from exc
