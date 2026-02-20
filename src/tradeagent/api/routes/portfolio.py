"""Portfolio API routes — summary and performance endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tradeagent.api.dependencies import get_db_session
from tradeagent.repositories.benchmark import BenchmarkRepository
from tradeagent.repositories.portfolio import PortfolioRepository
from tradeagent.repositories.stock import StockRepository
from tradeagent.schemas.portfolio import (
    BenchmarkSeries,
    PortfolioPerformanceResponse,
    PortfolioSnapshotResponse,
    PortfolioSummaryResponse,
    PositionResponse,
)

router = APIRouter()


@router.get("/portfolio/summary")
async def portfolio_summary(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> PortfolioSummaryResponse:
    """Return current portfolio summary with open positions and P&L."""
    settings = request.app.state.settings
    initial_capital = Decimal(str(settings.portfolio.initial_capital))

    positions = await PortfolioRepository.get_open_positions(session)
    latest_snapshot = await PortfolioRepository.get_latest_snapshot(session)

    position_responses: list[PositionResponse] = []
    invested = Decimal("0")
    total_cost_basis = Decimal("0")

    for pos in positions:
        latest_price = await StockRepository.get_latest_price(session, pos.stock_id)
        current_price = latest_price.close if latest_price else pos.avg_price

        market_value = (pos.quantity * current_price).quantize(Decimal("0.0001"))
        cost_basis = (pos.quantity * pos.avg_price).quantize(Decimal("0.0001"))
        unrealized_pnl = market_value - cost_basis
        invested += market_value
        total_cost_basis += cost_basis

        ticker = pos.stock.ticker if pos.stock else None

        position_responses.append(
            PositionResponse(
                id=pos.id,
                stock_id=pos.stock_id,
                ticker=ticker,
                quantity=pos.quantity,
                avg_price=pos.avg_price,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                weight_pct=None,  # set after total computed
                currency=pos.currency,
                opened_at=pos.opened_at,
                closed_at=pos.closed_at,
                status=pos.status,
            )
        )

    cash = initial_capital - total_cost_basis
    total_value = cash + invested

    # Compute weights
    for pr in position_responses:
        if total_value > 0 and pr.current_price is not None:
            pr.weight_pct = (
                pr.quantity * pr.current_price / total_value * 100
            ).quantize(Decimal("0.001"))

    if latest_snapshot is not None:
        daily_pnl = total_value - latest_snapshot.total_value
    else:
        daily_pnl = total_value - initial_capital

    if initial_capital > 0:
        cumulative_pnl_pct = (
            (total_value - initial_capital) / initial_capital * 100
        ).quantize(Decimal("0.0001"))
    else:
        cumulative_pnl_pct = Decimal("0")

    return PortfolioSummaryResponse(
        total_value=total_value,
        cash=cash,
        invested=invested,
        daily_pnl=daily_pnl.quantize(Decimal("0.0001")),
        cumulative_pnl_pct=cumulative_pnl_pct,
        num_positions=len(positions),
        positions=position_responses,
    )


@router.get("/portfolio/performance")
async def portfolio_performance(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
) -> PortfolioPerformanceResponse:
    """Return portfolio performance time series with benchmark overlays."""
    snapshots, _ = await PortfolioRepository.get_snapshots(
        session,
        start_date=start_date,
        end_date=end_date,
        limit=10000,
    )

    snapshot_responses = [PortfolioSnapshotResponse.model_validate(s) for s in snapshots]

    # Fetch benchmark data
    settings = request.app.state.settings
    benchmark_series: list[BenchmarkSeries] = []

    for bm_config in settings.benchmarks:
        benchmark = await BenchmarkRepository.get_by_symbol(session, bm_config.symbol)
        if benchmark is None:
            continue

        prices, _ = await BenchmarkRepository.get_prices(
            session,
            benchmark.id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

        if not prices:
            continue

        # Index to 100 from first price
        sorted_prices = sorted(prices, key=lambda p: p.date)
        base_price = sorted_prices[0].close if sorted_prices else Decimal("1")

        data = [
            {
                "date": p.date.isoformat(),
                "value": float((p.close / base_price * 100).quantize(Decimal("0.01"))),
            }
            for p in sorted_prices
            if base_price > 0
        ]

        benchmark_series.append(
            BenchmarkSeries(
                symbol=bm_config.symbol,
                name=bm_config.name,
                data=data,
            )
        )

    return PortfolioPerformanceResponse(
        snapshots=snapshot_responses,
        benchmarks=benchmark_series,
    )
