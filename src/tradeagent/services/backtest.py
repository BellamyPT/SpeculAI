"""Backtesting engine — replays historical data through the pipeline day-by-day."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tradeagent.adapters.base import PriceBar
from tradeagent.adapters.broker.simulated import SimulatedBroker
from tradeagent.adapters.llm.mock_llm import MockLLMAdapter
from tradeagent.adapters.market_data.mock_market_data import MockMarketDataAdapter
from tradeagent.adapters.news.mock_news import MockNewsAdapter
from tradeagent.config import Settings
from tradeagent.core.logging import get_logger
from tradeagent.core.types import BacktestStatus
from tradeagent.services.pipeline import PipelineService

log = get_logger(__name__)


@dataclass
class BacktestConfig:
    start_date: date
    end_date: date
    initial_capital: float = 50000.0


@dataclass
class BacktestMetrics:
    total_return_pct: float
    annualized_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate_pct: float
    total_trades: int
    avg_holding_days: float
    benchmark_returns: dict[str, float] = field(default_factory=dict)


@dataclass
class BacktestResult:
    backtest_run_id: UUID
    status: str
    config: BacktestConfig
    metrics: BacktestMetrics | None = None
    equity_curve: list[dict] | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    completed_at: datetime | None = None
    current_day: int = 0
    total_days: int = 0
    errors: list[str] = field(default_factory=list)


def _generate_trading_days(start: date, end: date) -> list[date]:
    """Generate business days (Mon-Fri) between start and end inclusive."""
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon=0 .. Fri=4
            days.append(current)
        current += timedelta(days=1)
    return days


class BacktestService:
    """Replay historical data day-by-day through the pipeline."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def run(self, config: BacktestConfig) -> BacktestResult:
        """Execute a full backtest. Updates result in-place for progress polling."""
        run_id = uuid4()
        result = BacktestResult(
            backtest_run_id=run_id,
            status=BacktestStatus.RUNNING,
            config=config,
        )

        trading_days = _generate_trading_days(config.start_date, config.end_date)
        result.total_days = len(trading_days)

        if not trading_days:
            result.status = BacktestStatus.FAILED
            result.errors.append("No trading days in the given range")
            result.completed_at = datetime.now(tz=timezone.utc)
            return result

        log.info(
            "backtest_started",
            run_id=str(run_id),
            start=str(config.start_date),
            end=str(config.end_date),
            trading_days=len(trading_days),
        )

        try:
            # Pre-load all market data once
            from tradeagent.adapters.market_data.yfinance_adapter import YFinanceAdapter

            yf_adapter = YFinanceAdapter()

            async with self._session_factory() as session:
                from tradeagent.repositories.stock import StockRepository

                stocks, _ = await StockRepository.get_all_active(session, limit=10000)

            if not stocks:
                result.status = BacktestStatus.FAILED
                result.errors.append("No active stocks found in database")
                result.completed_at = datetime.now(tz=timezone.utc)
                return result

            tickers = [s.ticker for s in stocks]

            # Fetch full date range + buffer for indicators
            buffer_start = config.start_date - timedelta(days=400)
            all_prices = await yf_adapter.fetch_prices(
                tickers, buffer_start, config.end_date
            )
            all_fundamentals = await yf_adapter.fetch_fundamentals(tickers)

            # Organize prices by ticker
            prices_by_ticker: dict[str, list[PriceBar]] = {}
            for ticker, vr in all_prices.items():
                prices_by_ticker[ticker] = sorted(vr.valid_bars, key=lambda b: b.date)

            # Set up mock adapters
            initial_capital = Decimal(str(config.initial_capital))
            broker = SimulatedBroker(initial_capital=initial_capital)
            mock_market_data = MockMarketDataAdapter()
            mock_market_data.load_fundamentals(all_fundamentals)
            mock_llm = MockLLMAdapter()
            mock_news = MockNewsAdapter()

            equity_curve: list[dict] = []
            trade_results: list[dict] = []

            # Day-by-day replay
            for i, day in enumerate(trading_days):
                result.current_day = i + 1

                try:
                    # Filter prices up to current day (no lookahead)
                    filtered_prices: dict[str, list[PriceBar]] = {}
                    for ticker, bars in prices_by_ticker.items():
                        filtered_prices[ticker] = [b for b in bars if b.date <= day]

                    mock_market_data.load_prices(filtered_prices)

                    # Set next-day open prices for order fills
                    next_day_idx = i + 1
                    if next_day_idx < len(trading_days):
                        next_day = trading_days[next_day_idx]
                        next_opens: dict[str, Decimal] = {}
                        for ticker, bars in prices_by_ticker.items():
                            for bar in bars:
                                if bar.date == next_day:
                                    next_opens[ticker] = bar.open
                                    break
                        broker.set_next_open_prices(next_opens)
                    else:
                        # Last day — use current close as fill price
                        closes: dict[str, Decimal] = {}
                        for ticker, bars in filtered_prices.items():
                            if bars:
                                closes[ticker] = bars[-1].close
                        broker.set_next_open_prices(closes)

                    # Run pipeline with mock adapters
                    pipeline = PipelineService(
                        session_factory=self._session_factory,
                        settings=self._settings,
                        market_data_adapter=mock_market_data,
                        llm_adapter=mock_llm,
                        news_adapter=mock_news,
                        broker_adapter=broker,
                    )

                    await pipeline.run()

                    # Record equity curve point
                    portfolio_value = broker.get_portfolio_value()
                    equity_curve.append({
                        "date": day.isoformat(),
                        "value": float(portfolio_value),
                    })

                except Exception as exc:
                    result.errors.append(f"Day {day}: {exc}")
                    log.warning(
                        "backtest_day_failed",
                        run_id=str(run_id),
                        day=str(day),
                        exc_info=True,
                    )
                    # Still record equity point with last known value
                    if equity_curve:
                        equity_curve.append({
                            "date": day.isoformat(),
                            "value": equity_curve[-1]["value"],
                        })

            result.equity_curve = equity_curve

            # Compute metrics
            result.metrics = self._compute_metrics(
                equity_curve, config.initial_capital, trading_days
            )

            result.status = BacktestStatus.COMPLETED

        except Exception as exc:
            result.status = BacktestStatus.FAILED
            result.errors.append(f"Backtest failed: {exc}")
            log.error("backtest_failed", run_id=str(run_id), exc_info=True)

        result.completed_at = datetime.now(tz=timezone.utc)
        log.info(
            "backtest_completed",
            run_id=str(run_id),
            status=result.status,
            total_days=result.total_days,
        )
        return result

    def _compute_metrics(
        self,
        equity_curve: list[dict],
        initial_capital: float,
        trading_days: list[date],
    ) -> BacktestMetrics:
        """Compute performance metrics from the equity curve."""
        if not equity_curve:
            return BacktestMetrics(
                total_return_pct=0.0,
                annualized_return_pct=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                win_rate_pct=0.0,
                total_trades=0,
                avg_holding_days=0.0,
            )

        values = [p["value"] for p in equity_curve]
        final = values[-1]
        total_return = (final - initial_capital) / initial_capital * 100

        num_days = len(trading_days)
        annualized = self._compute_annualized_return(total_return / 100, num_days)
        max_dd = self._compute_max_drawdown(values)
        sharpe = self._compute_sharpe_ratio(values)

        return BacktestMetrics(
            total_return_pct=round(total_return, 2),
            annualized_return_pct=round(annualized, 2),
            max_drawdown_pct=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 2),
            win_rate_pct=0.0,  # requires trade-level P&L tracking
            total_trades=0,  # requires counting from broker
            avg_holding_days=0.0,
        )

    @staticmethod
    def _compute_annualized_return(total_return_frac: float, num_days: int) -> float:
        """Annualize return: ((1 + r) ^ (252/days) - 1) * 100."""
        if num_days <= 0:
            return 0.0
        try:
            return ((1 + total_return_frac) ** (252 / num_days) - 1) * 100
        except (OverflowError, ValueError):
            return 0.0

    @staticmethod
    def _compute_max_drawdown(values: list[float]) -> float:
        """Compute max drawdown percentage from equity values."""
        if len(values) < 2:
            return 0.0
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            if peak > 0:
                dd = (peak - v) / peak * 100
                if dd > max_dd:
                    max_dd = dd
        return max_dd

    @staticmethod
    def _compute_sharpe_ratio(values: list[float]) -> float:
        """Compute annualized Sharpe ratio (risk-free rate = 0)."""
        if len(values) < 3:
            return 0.0

        # Daily returns
        returns = []
        for i in range(1, len(values)):
            if values[i - 1] > 0:
                returns.append((values[i] - values[i - 1]) / values[i - 1])

        if not returns:
            return 0.0

        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        std_r = math.sqrt(variance)

        if std_r == 0:
            return 0.0

        return (mean_r / std_r) * math.sqrt(252)
