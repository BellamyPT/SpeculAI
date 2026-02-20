"""Pipeline orchestrator — runs the daily 10-step analysis workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tradeagent.adapters.base import (
    BrokerAdapter,
    LLMAdapter,
    MarketDataAdapter,
    NewsAdapter,
    NewsItem,
    OrderRequest,
)
from tradeagent.config import Settings
from tradeagent.core.exceptions import DataIngestionError, LLMError
from tradeagent.core.logging import get_logger
from tradeagent.core.types import PipelineStatus, Side, TradeStatus
from tradeagent.repositories.portfolio import PortfolioRepository
from tradeagent.repositories.stock import StockRepository
from tradeagent.repositories.trade import TradeRepository
from tradeagent.services.memory import MemoryItem, MemoryService
from tradeagent.services.report_generator import ReportGenerator
from tradeagent.services.risk_manager import (
    ApprovedTrade,
    PortfolioState,
    PositionInfo,
    RiskManager,
    RiskValidationResult,
    TradeProposal,
)
from tradeagent.services.screening import CandidateScore, ScreeningService
from tradeagent.services.technical_analysis import TechnicalAnalysisService

log = get_logger(__name__)


@dataclass
class PipelineRunResult:
    """Result of a pipeline run."""

    pipeline_run_id: UUID
    status: PipelineStatus
    started_at: datetime
    completed_at: datetime | None = None
    stocks_analyzed: int = 0
    candidates_screened: int = 0
    trades_approved: int = 0
    trades_executed: int = 0
    errors: list[str] = field(default_factory=list)


class PipelineService:
    """Orchestrate the daily analysis pipeline."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        market_data_adapter: MarketDataAdapter,
        llm_adapter: LLMAdapter,
        news_adapter: NewsAdapter,
        broker_adapter: BrokerAdapter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._market_data = market_data_adapter
        self._llm = llm_adapter
        self._news = news_adapter
        self._broker = broker_adapter

        # Sub-services
        self._ta = TechnicalAnalysisService(settings.technical_analysis)
        self._screener = ScreeningService(settings.screening)
        self._risk_manager = RiskManager(settings.portfolio)
        self._memory = MemoryService(settings.memory)
        self._report_gen = ReportGenerator()

    async def run(self) -> PipelineRunResult:
        """Execute the full pipeline. Returns result even on partial failure."""
        pipeline_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)

        result = PipelineRunResult(
            pipeline_run_id=pipeline_run_id,
            status=PipelineStatus.RUNNING,
            started_at=started_at,
        )

        log.info("pipeline_started", pipeline_run_id=str(pipeline_run_id))

        async with self._session_factory() as session:
            try:
                # Step 1: Fetch market data
                stocks_data = await self._step_fetch_market_data(session)
                result.stocks_analyzed = len(stocks_data)

                if not stocks_data:
                    raise DataIngestionError("No market data fetched")

                # Step 2: Compute indicators
                stocks_with_indicators = await self._step_compute_indicators(
                    session, stocks_data
                )

                # Step 3: Screen candidates
                portfolio_state = await self._build_portfolio_state(session)
                portfolio_stock_ids = set(portfolio_state.positions.keys())
                candidates = self._step_screen_candidates(
                    stocks_with_indicators, portfolio_stock_ids
                )
                result.candidates_screened = len(candidates)

                # Step 4: Fetch news (non-critical)
                news = await self._step_fetch_news(candidates, result)

                # Step 5: Retrieve memory
                memory = await self._step_retrieve_memory(session, candidates)

                # Step 6: Build analysis package
                analysis_package = self._step_build_analysis_package(
                    portfolio_state, candidates, news, memory
                )

                # Step 7: LLM analysis
                llm_response = await self._step_llm_analyze(analysis_package)

                # Step 8: Risk validation
                proposals = self._parse_llm_proposals(
                    llm_response.parsed, candidates
                )
                risk_result = self._step_risk_validate(proposals, portfolio_state)
                result.trades_approved = len(risk_result.approved)

                # Step 9: Generate reports
                await self._step_generate_reports(
                    session, pipeline_run_id, candidates,
                    risk_result, news, memory, portfolio_state,
                )

                # Step 10: Execute trades
                if self._broker and risk_result.approved:
                    executed = await self._step_execute_trades(
                        session, risk_result.approved, pipeline_run_id, result
                    )
                    result.trades_executed = executed

                await session.commit()

                if result.errors:
                    result.status = PipelineStatus.PARTIAL_FAILURE
                else:
                    result.status = PipelineStatus.SUCCESS

            except (DataIngestionError, LLMError) as exc:
                result.status = PipelineStatus.FAILED
                result.errors.append(str(exc))
                log.error(
                    "pipeline_critical_failure",
                    pipeline_run_id=str(pipeline_run_id),
                    error=str(exc),
                )
            except Exception as exc:
                result.status = PipelineStatus.FAILED
                result.errors.append(f"Unexpected error: {exc}")
                log.error(
                    "pipeline_unexpected_failure",
                    pipeline_run_id=str(pipeline_run_id),
                    exc_info=True,
                )

        result.completed_at = datetime.now(tz=timezone.utc)
        log.info(
            "pipeline_completed",
            pipeline_run_id=str(pipeline_run_id),
            status=result.status,
            stocks_analyzed=result.stocks_analyzed,
            trades_approved=result.trades_approved,
            trades_executed=result.trades_executed,
            errors=result.errors,
        )
        return result

    # ── Pipeline steps ──────────────────────────────────────────────

    async def _step_fetch_market_data(
        self, session: AsyncSession
    ) -> list[dict]:
        """Step 1: Fetch prices and fundamentals for all active stocks."""
        stocks, _ = await StockRepository.get_all_active(session, limit=10000)
        if not stocks:
            return []

        tickers = [s.ticker for s in stocks]
        ticker_to_stock = {s.ticker: s for s in stocks}

        end = date.today()
        start = end - timedelta(days=365)

        log.info("fetching_market_data", num_tickers=len(tickers))

        validation_results = await self._market_data.fetch_prices(tickers, start, end)
        fundamentals = await self._market_data.fetch_fundamentals(tickers)

        stocks_data: list[dict] = []
        for ticker, vr in validation_results.items():
            stock = ticker_to_stock.get(ticker)
            if stock is None:
                continue

            # Persist prices
            if vr.valid_bars:
                price_dicts = [
                    {
                        "stock_id": stock.id,
                        "date": bar.date,
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "adj_close": bar.adj_close,
                        "volume": bar.volume,
                    }
                    for bar in vr.valid_bars
                ]
                await StockRepository.bulk_upsert_prices(session, price_dicts)

            # Persist fundamentals
            fund = fundamentals.get(ticker)
            if fund:
                fund_kwargs = {}
                for field_name in [
                    "market_cap", "pe_ratio", "forward_pe", "peg_ratio",
                    "price_to_book", "price_to_sales", "dividend_yield", "eps",
                    "revenue_growth", "earnings_growth", "profit_margin",
                    "debt_to_equity", "current_ratio", "beta",
                ]:
                    val = getattr(fund, field_name, None)
                    if val is not None:
                        fund_kwargs[field_name] = val
                if fund_kwargs:
                    await StockRepository.upsert_fundamental(
                        session,
                        stock_id=stock.id,
                        snapshot_date=end,
                        **fund_kwargs,
                    )

                # Update stock metadata
                update_fields = {}
                if fund.name and fund.name != stock.name:
                    update_fields["name"] = fund.name
                if fund.sector and fund.sector != stock.sector:
                    update_fields["sector"] = fund.sector
                if fund.industry and fund.industry != stock.industry:
                    update_fields["industry"] = fund.industry
                if update_fields:
                    await StockRepository.update(session, stock.id, **update_fields)

            stocks_data.append({
                "stock_id": stock.id,
                "ticker": ticker,
                "sector": stock.sector,
                "prices": vr.valid_bars,
                "fundamentals": {
                    "market_cap": getattr(fund, "market_cap", None) if fund else None,
                    "pe_ratio": getattr(fund, "pe_ratio", None) if fund else None,
                },
            })

        await session.flush()
        log.info("market_data_fetched", stocks_count=len(stocks_data))
        return stocks_data

    async def _step_compute_indicators(
        self, session: AsyncSession, stocks_data: list[dict]
    ) -> list[dict]:
        """Step 2: Compute technical indicators for each stock."""
        result = []
        for item in stocks_data:
            prices = item.get("prices", [])
            if not prices:
                continue
            try:
                df = self._ta.prices_to_dataframe(prices)
                indicators = self._ta.compute_indicators(df)
                item["indicators"] = indicators
                result.append(item)
            except Exception:
                log.warning(
                    "indicator_computation_failed",
                    ticker=item.get("ticker"),
                    exc_info=True,
                )
        return result

    def _step_screen_candidates(
        self,
        stocks_with_indicators: list[dict],
        portfolio_stock_ids: set[int],
    ) -> list[CandidateScore]:
        """Step 3: Score and rank candidates."""
        return self._screener.score_and_rank(
            stocks_with_indicators, portfolio_stock_ids
        )

    async def _step_fetch_news(
        self,
        candidates: list[CandidateScore],
        result: PipelineRunResult,
    ) -> list[NewsItem]:
        """Step 4: Fetch news. Non-critical — continues on failure."""
        try:
            topics = list(set(
                self._settings.news.sectors[:5]
                + [c.ticker for c in candidates[:5]]
            ))
            return await self._news.query_news(topics)
        except Exception as exc:
            result.errors.append(f"News fetch failed: {exc}")
            log.warning("news_fetch_failed", exc_info=True)
            return []

    async def _step_retrieve_memory(
        self,
        session: AsyncSession,
        candidates: list[CandidateScore],
    ) -> dict[int, list[MemoryItem]]:
        """Step 5: Retrieve decision memory per candidate."""
        memory: dict[int, list[MemoryItem]] = {}
        for candidate in candidates:
            try:
                rsi = candidate.indicators.get("rsi")
                macd = candidate.indicators.get("macd")
                macd_dir = macd.get("direction") if isinstance(macd, dict) else None
                items = await self._memory.retrieve_memory(
                    session,
                    stock_id=candidate.stock_id,
                    ticker=candidate.ticker,
                    sector=candidate.sector,
                    rsi_value=float(rsi) if rsi is not None else None,
                    macd_direction=macd_dir,
                )
                if items:
                    memory[candidate.stock_id] = items
            except Exception:
                log.warning(
                    "memory_retrieval_failed",
                    ticker=candidate.ticker,
                    exc_info=True,
                )
        return memory

    def _step_build_analysis_package(
        self,
        portfolio_state: PortfolioState,
        candidates: list[CandidateScore],
        news: list[NewsItem],
        memory: dict[int, list[MemoryItem]],
    ) -> dict:
        """Step 6: Assemble the analysis package for the LLM."""
        candidate_dicts = []
        for c in candidates:
            mem_items = memory.get(c.stock_id, [])
            candidate_dicts.append({
                "ticker": c.ticker,
                "sector": c.sector,
                "total_score": c.total_score,
                "rsi": c.indicators.get("rsi"),
                "macd_direction": (
                    c.indicators.get("macd", {}).get("direction")
                    if isinstance(c.indicators.get("macd"), dict)
                    else None
                ),
                "in_portfolio": c.in_portfolio,
                "fundamentals": c.fundamentals,
            })

        news_dicts = [
            {
                "headline": n.headline,
                "summary": n.summary,
                "source": n.source,
            }
            for n in news
        ]

        all_memory = []
        for stock_id, items in memory.items():
            all_memory.extend(self._memory.format_memory_for_prompt(items))

        return {
            "portfolio_state": {
                "total_value": str(portfolio_state.total_value),
                "cash_available": str(portfolio_state.cash_available),
                "num_positions": portfolio_state.num_open_positions,
            },
            "candidates": candidate_dicts,
            "news": news_dicts,
            "memory": all_memory,
        }

    async def _step_llm_analyze(self, analysis_package: dict):
        """Step 7: Call LLM for analysis."""
        return await self._llm.analyze(analysis_package)

    def _parse_llm_proposals(
        self,
        parsed: dict,
        candidates: list[CandidateScore],
    ) -> list[TradeProposal]:
        """Parse LLM recommendations into TradeProposal DTOs."""
        candidate_map = {c.ticker: c for c in candidates}
        recommendations = parsed.get("recommendations", [])
        if not recommendations:
            recommendations = parsed.get("trades", [])

        proposals: list[TradeProposal] = []
        for rec in recommendations:
            ticker = rec.get("ticker", "")
            action = rec.get("action", "").upper()
            if action not in ("BUY", "SELL"):
                continue

            candidate = candidate_map.get(ticker)
            if candidate is None:
                continue

            proposals.append(
                TradeProposal(
                    ticker=ticker,
                    stock_id=candidate.stock_id,
                    action=action,
                    confidence=float(rec.get("confidence", 0)),
                    reasoning=rec.get("reasoning", ""),
                    suggested_allocation_pct=float(
                        rec.get("suggested_allocation_pct", 3.0)
                    ),
                    current_price=Decimal(
                        str(candidate.indicators.get("latest_close", 0))
                    ),
                    currency=self._settings.portfolio.base_currency,
                )
            )
        return proposals

    def _step_risk_validate(
        self,
        proposals: list[TradeProposal],
        portfolio_state: PortfolioState,
    ) -> RiskValidationResult:
        """Step 8: Validate proposals through risk manager."""
        return self._risk_manager.validate_trades(proposals, portfolio_state)

    async def _step_generate_reports(
        self,
        session: AsyncSession,
        pipeline_run_id: UUID,
        candidates: list[CandidateScore],
        risk_result: RiskValidationResult,
        news: list[NewsItem],
        memory: dict[int, list[MemoryItem]],
        portfolio_state: PortfolioState,
    ) -> None:
        """Step 9: Generate decision reports."""
        await self._report_gen.generate_reports(
            session, pipeline_run_id, candidates,
            risk_result, news, memory, portfolio_state,
        )

    async def _step_execute_trades(
        self,
        session: AsyncSession,
        approved: list[ApprovedTrade],
        pipeline_run_id: UUID,
        result: PipelineRunResult,
    ) -> int:
        """Step 10: Execute approved trades via broker."""
        executed = 0
        for trade in approved:
            try:
                order = OrderRequest(
                    ticker=trade.ticker,
                    side=trade.side,
                    quantity=trade.quantity,
                )
                order_status = await self._broker.place_order(order)

                status = (
                    TradeStatus.FILLED
                    if order_status.status == "FILLED"
                    else TradeStatus.FAILED
                )
                filled_price = (
                    order_status.filled_price
                    if order_status.filled_price
                    else trade.estimated_value / trade.quantity
                )
                total_val = (
                    order_status.filled_quantity * filled_price
                    if order_status.filled_quantity
                    else trade.estimated_value
                )

                await TradeRepository.create(
                    session,
                    stock_id=trade.stock_id,
                    side=trade.side,
                    quantity=order_status.filled_quantity or trade.quantity,
                    price=filled_price,
                    total_value=total_val,
                    currency=self._settings.portfolio.base_currency,
                    status=status,
                    broker_order_id=order_status.broker_order_id,
                    executed_at=order_status.filled_at or datetime.now(tz=timezone.utc),
                )

                # Update position
                if status == TradeStatus.FILLED:
                    await self._update_position(
                        session, trade, filled_price, order_status.filled_quantity
                    )
                    executed += 1

            except Exception as exc:
                result.errors.append(
                    f"Trade execution failed for {trade.ticker}: {exc}"
                )
                log.error(
                    "trade_execution_failed",
                    ticker=trade.ticker,
                    exc_info=True,
                )

        return executed

    async def _update_position(
        self,
        session: AsyncSession,
        trade: ApprovedTrade,
        filled_price: Decimal,
        filled_quantity: Decimal | None,
    ) -> None:
        """Update or create position after a filled trade."""
        qty = filled_quantity or trade.quantity
        position = await PortfolioRepository.get_open_position_by_stock(
            session, trade.stock_id
        )

        if trade.side == Side.BUY:
            if position:
                # Average up
                total_qty = position.quantity + qty
                total_cost = position.quantity * position.avg_price + qty * filled_price
                new_avg = (total_cost / total_qty).quantize(Decimal("0.0001"))
                await PortfolioRepository.update_position(
                    position.id, quantity=total_qty, avg_price=new_avg
                )
            else:
                await PortfolioRepository.create_position(
                    session,
                    stock_id=trade.stock_id,
                    quantity=qty,
                    avg_price=filled_price,
                    currency=self._settings.portfolio.base_currency,
                    opened_at=datetime.now(tz=timezone.utc),
                )
        elif trade.side == Side.SELL and position:
            remaining = position.quantity - qty
            if remaining <= 0:
                await PortfolioRepository.close_position(
                    session, position.id, datetime.now(tz=timezone.utc)
                )
            else:
                await PortfolioRepository.update_position(
                    session, position.id, quantity=remaining
                )

    # ── Helpers ──────────────────────────────────────────────────────

    async def _build_portfolio_state(
        self, session: AsyncSession
    ) -> PortfolioState:
        """Build current portfolio state from DB."""
        positions = await PortfolioRepository.get_open_positions(session)
        initial_capital = Decimal(str(self._settings.portfolio.initial_capital))

        position_infos: dict[int, PositionInfo] = {}
        total_invested = Decimal("0")

        for pos in positions:
            latest = await StockRepository.get_latest_price(session, pos.stock_id)
            current_price = latest.close if latest else pos.avg_price
            market_value = (pos.quantity * current_price).quantize(Decimal("0.0001"))
            total_invested += market_value

            ticker = pos.stock.ticker if pos.stock else ""

            position_infos[pos.stock_id] = PositionInfo(
                stock_id=pos.stock_id,
                ticker=ticker,
                quantity=pos.quantity,
                avg_price=pos.avg_price,
                current_price=current_price,
                market_value=market_value,
                weight_pct=0.0,  # computed below
            )

        total_cost_basis = sum(
            (pos.quantity * pos.avg_price).quantize(Decimal("0.0001"))
            for pos in positions
        )
        cash = initial_capital - total_cost_basis
        total_value = cash + total_invested

        # Compute weights
        if total_value > 0:
            for pi in position_infos.values():
                object.__setattr__(
                    pi, "weight_pct",
                    float(pi.market_value / total_value * 100)
                )

        return PortfolioState(
            total_value=total_value,
            cash_available=cash,
            positions=position_infos,
            num_open_positions=len(positions),
        )
