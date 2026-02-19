from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import cast, func, select, Float
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from tradeagent.core.exceptions import RepositoryError
from tradeagent.models.decision import DecisionContextItem, DecisionReport
from tradeagent.models.stock import Stock


class DecisionRepository:
    """Data access layer for DecisionReport and DecisionContextItem."""

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        stock_id: int,
        pipeline_run_id: object,
        action: str,
        confidence: object,
        reasoning: str,
        technical_summary: dict,
        news_summary: dict,
        portfolio_state: dict,
        memory_references: dict | None = None,
        is_backtest: bool = False,
        backtest_run_id: object | None = None,
    ) -> DecisionReport:
        try:
            report = DecisionReport(
                stock_id=stock_id,
                pipeline_run_id=pipeline_run_id,
                action=action,
                confidence=confidence,
                reasoning=reasoning,
                technical_summary=technical_summary,
                news_summary=news_summary,
                portfolio_state=portfolio_state,
                memory_references=memory_references,
                is_backtest=is_backtest,
                backtest_run_id=backtest_run_id,
            )
            session.add(report)
            await session.flush()
            return report
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to create decision report") from exc

    @staticmethod
    async def get_by_id(
        session: AsyncSession, report_id: int
    ) -> DecisionReport | None:
        try:
            result = await session.execute(
                select(DecisionReport)
                .options(joinedload(DecisionReport.context_items))
                .where(DecisionReport.id == report_id)
            )
            return result.unique().scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get decision report {report_id}"
            ) from exc

    @staticmethod
    async def get_list(
        session: AsyncSession,
        *,
        ticker: str | None = None,
        action: str | None = None,
        min_confidence: float | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        include_backtest: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DecisionReport], int]:
        """Get filtered, paginated decision report list."""
        try:
            filters = DecisionRepository._build_list_filters(
                ticker=ticker,
                action=action,
                min_confidence=min_confidence,
                start_date=start_date,
                end_date=end_date,
                include_backtest=include_backtest,
            )

            base = select(DecisionReport).join(DecisionReport.stock)
            for f in filters:
                base = base.where(f)

            count_q = select(func.count()).select_from(base.subquery())
            total = (await session.execute(count_q)).scalar_one()

            data_q = (
                base.options(joinedload(DecisionReport.stock))
                .order_by(DecisionReport.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = (await session.execute(data_q)).unique().scalars().all()
            return list(rows), total
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to list decision reports") from exc

    @staticmethod
    async def update_outcome(
        session: AsyncSession,
        report_id: int,
        *,
        outcome_pnl: object,
        outcome_benchmark_delta: object,
        outcome_assessed_at: datetime,
    ) -> DecisionReport:
        try:
            report = await session.get(DecisionReport, report_id)
            if report is None:
                raise RepositoryError(f"Decision report {report_id} not found")
            report.outcome_pnl = outcome_pnl
            report.outcome_benchmark_delta = outcome_benchmark_delta
            report.outcome_assessed_at = outcome_assessed_at
            await session.flush()
            return report
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to update outcome for report {report_id}"
            ) from exc

    @staticmethod
    async def get_unassessed(
        session: AsyncSession,
        older_than: datetime,
        *,
        is_backtest: bool = False,
        limit: int | None = None,
    ) -> list[DecisionReport]:
        try:
            q = (
                select(DecisionReport)
                .where(
                    DecisionReport.outcome_assessed_at.is_(None),
                    DecisionReport.is_backtest == is_backtest,
                    DecisionReport.created_at <= older_than,
                )
                .order_by(DecisionReport.created_at)
            )
            if limit is not None:
                q = q.limit(limit)
            result = await session.execute(q)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to get unassessed decisions") from exc

    # ── Context items ───────────────────────────────────────────────

    @staticmethod
    async def create_context_item(
        session: AsyncSession,
        *,
        decision_report_id: int,
        context_type: str,
        source: str,
        content: str,
        relevance_score: object | None = None,
    ) -> DecisionContextItem:
        try:
            item = DecisionContextItem(
                decision_report_id=decision_report_id,
                context_type=context_type,
                source=source,
                content=content,
                relevance_score=relevance_score,
            )
            session.add(item)
            await session.flush()
            return item
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to create context item") from exc

    @staticmethod
    async def bulk_create_context_items(
        session: AsyncSession, items: list[dict]
    ) -> list[DecisionContextItem]:
        if not items:
            return []
        try:
            objects = [DecisionContextItem(**i) for i in items]
            session.add_all(objects)
            await session.flush()
            return objects
        except SQLAlchemyError as exc:
            raise RepositoryError("Failed to bulk create context items") from exc

    # ── Memory retrieval queries ────────────────────────────────────

    @staticmethod
    async def get_by_ticker(
        session: AsyncSession,
        stock_id: int,
        *,
        limit: int = 10,
        is_backtest: bool = False,
    ) -> list[DecisionReport]:
        """Get recent decisions for a specific stock (memory by ticker)."""
        try:
            result = await session.execute(
                select(DecisionReport)
                .where(
                    DecisionReport.stock_id == stock_id,
                    DecisionReport.is_backtest == is_backtest,
                )
                .order_by(DecisionReport.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get decisions by ticker for stock {stock_id}"
            ) from exc

    @staticmethod
    async def get_by_sector(
        session: AsyncSession,
        sector: str,
        *,
        exclude_stock_id: int | None = None,
        limit: int = 5,
        is_backtest: bool = False,
    ) -> list[DecisionReport]:
        """Get top decisions by sector, ordered by outcome P&L (memory by sector)."""
        try:
            q = (
                select(DecisionReport)
                .join(Stock, DecisionReport.stock_id == Stock.id)
                .where(
                    Stock.sector == sector,
                    DecisionReport.is_backtest == is_backtest,
                )
            )
            if exclude_stock_id is not None:
                q = q.where(DecisionReport.stock_id != exclude_stock_id)

            q = q.order_by(
                DecisionReport.outcome_pnl.desc().nulls_last()
            ).limit(limit)

            result = await session.execute(q)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(
                f"Failed to get decisions by sector {sector}"
            ) from exc

    @staticmethod
    async def get_by_similar_signals(
        session: AsyncSession,
        *,
        rsi_value: float,
        rsi_tolerance: float = 10.0,
        macd_direction: str | None = None,
        is_backtest: bool = False,
        limit: int = 5,
    ) -> list[DecisionReport]:
        """Get decisions with similar technical signals (JSONB extraction).

        Filters on technical_summary->>'rsi' within [rsi_value ± tolerance],
        and optionally matches technical_summary->'macd'->>'direction'.
        """
        try:
            rsi_col = cast(
                DecisionReport.technical_summary["rsi"].as_string(), Float
            )
            rsi_low = rsi_value - rsi_tolerance
            rsi_high = rsi_value + rsi_tolerance

            q = (
                select(DecisionReport)
                .where(
                    DecisionReport.is_backtest == is_backtest,
                    rsi_col.isnot(None),
                    rsi_col >= rsi_low,
                    rsi_col <= rsi_high,
                )
            )
            if macd_direction is not None:
                macd_dir_col = DecisionReport.technical_summary["macd"]["direction"].as_string()
                q = q.where(macd_dir_col == macd_direction)

            q = q.order_by(
                DecisionReport.outcome_pnl.desc().nulls_last()
            ).limit(limit)

            result = await session.execute(q)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(
                "Failed to get decisions by similar signals"
            ) from exc

    # ── Private helpers ─────────────────────────────────────────────

    @staticmethod
    def _build_list_filters(
        *,
        ticker: str | None,
        action: str | None,
        min_confidence: float | None,
        start_date: date | None,
        end_date: date | None,
        include_backtest: bool,
    ) -> list:
        """Build WHERE clause conditions for decision report listing."""
        filters = []
        if not include_backtest:
            filters.append(DecisionReport.is_backtest.is_(False))
        if ticker is not None:
            filters.append(Stock.ticker == ticker)
        if action is not None:
            filters.append(DecisionReport.action == action)
        if min_confidence is not None:
            filters.append(DecisionReport.confidence >= min_confidence)
        if start_date is not None:
            filters.append(
                DecisionReport.created_at >= datetime.combine(start_date, datetime.min.time())
            )
        if end_date is not None:
            filters.append(
                DecisionReport.created_at <= datetime.combine(end_date, datetime.max.time())
            )
        return filters
