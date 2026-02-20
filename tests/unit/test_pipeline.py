"""Unit tests for PipelineService."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tradeagent.adapters.base import (
    FundamentalSnapshot,
    LLMResponse,
    NewsItem,
    OrderStatus,
    PriceBar,
    ValidationResult,
)
from tradeagent.config import Settings
from tradeagent.core.exceptions import DataIngestionError, LLMError
from tradeagent.core.types import PipelineStatus
from tradeagent.services.pipeline import PipelineRunResult, PipelineService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_factory():
    """Return a MagicMock that acts as an async context-manager session factory."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory.return_value = mock_session_ctx
    return mock_session_factory, mock_session


def _make_stock(stock_id: int, ticker: str, sector: str = "Technology") -> MagicMock:
    stock = MagicMock()
    stock.id = stock_id
    stock.ticker = ticker
    stock.sector = sector
    stock.name = f"{ticker} Inc."
    stock.industry = "Software"
    return stock


def _make_price_bar(ticker: str) -> PriceBar:
    return PriceBar(
        ticker=ticker,
        date=date(2024, 1, 2),
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("148.00"),
        close=Decimal("152.00"),
        adj_close=Decimal("152.00"),
        volume=1_000_000,
    )


def _make_fundamental(ticker: str) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        ticker=ticker,
        snapshot_date=date.today(),
        name=f"{ticker} Inc.",
        sector="Technology",
        industry="Software",
        market_cap=Decimal("3000000000000"),
        pe_ratio=Decimal("28.5"),
        beta=Decimal("1.2"),
    )


def _make_market_data_adapter(tickers: list[str]):
    adapter = AsyncMock()
    adapter.fetch_prices = AsyncMock(
        return_value={
            t: ValidationResult(
                ticker=t,
                valid_bars=[_make_price_bar(t)],
            )
            for t in tickers
        }
    )
    adapter.fetch_fundamentals = AsyncMock(
        return_value={t: _make_fundamental(t) for t in tickers}
    )
    return adapter


def _make_llm_adapter(tickers: list[str]):
    adapter = AsyncMock()
    adapter.analyze = AsyncMock(
        return_value=LLMResponse(
            raw_text='{"recommendations": []}',
            parsed={
                "recommendations": [
                    {
                        "ticker": tickers[0],
                        "action": "BUY",
                        "confidence": 0.8,
                        "reasoning": "Strong momentum signals",
                        "suggested_allocation_pct": 3.0,
                    }
                ]
            },
            token_count=500,
            response_time_seconds=1.5,
            parse_success=True,
        )
    )
    return adapter


def _make_news_adapter():
    adapter = AsyncMock()
    adapter.query_news = AsyncMock(
        return_value=[
            NewsItem(
                source="Reuters",
                headline="Tech stocks rally",
                summary="Technology sector continues strong performance",
                published_at=datetime.now(tz=timezone.utc),
                url="https://reuters.com/tech-rally",
                relevance_score=0.9,
            )
        ]
    )
    return adapter


def _make_broker_adapter():
    adapter = AsyncMock()
    adapter.place_order = AsyncMock(
        return_value=OrderStatus(
            broker_order_id=str(uuid4()),
            ticker="AAPL",
            side="BUY",
            status="FILLED",
            filled_quantity=Decimal("5.000000"),
            filled_price=Decimal("152.00"),
            filled_at=datetime.now(tz=timezone.utc),
        )
    )
    return adapter


def _make_pipeline_service(
    settings: Settings,
    tickers: list[str],
    broker_adapter=None,
) -> tuple[PipelineService, MagicMock, MagicMock, MagicMock, MagicMock]:
    session_factory, mock_session = _make_session_factory()
    market_data = _make_market_data_adapter(tickers)
    llm = _make_llm_adapter(tickers)
    news = _make_news_adapter()
    svc = PipelineService(
        session_factory=session_factory,
        settings=settings,
        market_data_adapter=market_data,
        llm_adapter=llm,
        news_adapter=news,
        broker_adapter=broker_adapter,
    )
    return svc, mock_session, market_data, llm, news


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("tradeagent.services.pipeline.PortfolioRepository")
@patch("tradeagent.services.pipeline.StockRepository")
@patch("tradeagent.services.pipeline.TradeRepository")
@patch("tradeagent.services.pipeline.ReportGenerator")
@patch("tradeagent.services.pipeline.MemoryService")
@patch("tradeagent.services.pipeline.RiskManager")
@patch("tradeagent.services.pipeline.ScreeningService")
@patch("tradeagent.services.pipeline.TechnicalAnalysisService")
async def test_pipeline_success(
    MockTA,
    MockScreener,
    MockRisk,
    MockMemory,
    MockReportGen,
    MockTradeRepo,
    MockStockRepo,
    MockPortfolioRepo,
    settings: Settings,
):
    """Full happy-path pipeline run with 2 stocks should succeed."""
    tickers = ["AAPL", "MSFT"]
    stocks = [_make_stock(1, "AAPL"), _make_stock(2, "MSFT")]

    # StockRepository mocks
    MockStockRepo.get_all_active = AsyncMock(return_value=(stocks, 2))
    MockStockRepo.bulk_upsert_prices = AsyncMock()
    MockStockRepo.upsert_fundamental = AsyncMock()
    MockStockRepo.update = AsyncMock()
    MockStockRepo.get_latest_price = AsyncMock(return_value=MagicMock(close=Decimal("152.00")))

    # PortfolioRepository mocks
    mock_position = MagicMock()
    mock_position.stock_id = 1
    mock_position.quantity = Decimal("5")
    mock_position.avg_price = Decimal("145.00")
    mock_position.stock = MagicMock(ticker="AAPL")
    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[mock_position])
    MockPortfolioRepo.get_open_position_by_stock = AsyncMock(return_value=None)
    MockPortfolioRepo.create_position = AsyncMock(return_value=MagicMock())

    # TechnicalAnalysisService mock — price_to_dataframe and compute_indicators
    mock_ta_instance = MockTA.return_value
    mock_ta_instance.prices_to_dataframe = MagicMock(return_value=MagicMock())
    mock_ta_instance.compute_indicators = MagicMock(
        return_value={"rsi": 45.0, "macd": {"direction": "bullish", "histogram": 0.5}, "latest_close": 152.0}
    )

    # ScreeningService mock
    mock_candidate = MagicMock()
    mock_candidate.stock_id = 1
    mock_candidate.ticker = "AAPL"
    mock_candidate.sector = "Technology"
    mock_candidate.total_score = 0.75
    mock_candidate.indicators = {"rsi": 45.0, "macd": {"direction": "bullish"}, "latest_close": 152.0}
    mock_candidate.fundamentals = {"market_cap": 3_000_000_000_000, "pe_ratio": 28.5}
    mock_candidate.in_portfolio = False
    mock_screener_instance = MockScreener.return_value
    mock_screener_instance.score_and_rank = MagicMock(return_value=[mock_candidate])

    # RiskManager mock
    from tradeagent.services.risk_manager import ApprovedTrade, RiskValidationResult
    mock_approved = ApprovedTrade(
        ticker="AAPL",
        stock_id=1,
        action="BUY",
        side="BUY",
        quantity=Decimal("5.000000"),
        estimated_value=Decimal("760.00"),
        confidence=0.8,
        reasoning="Strong momentum signals",
    )
    mock_risk_result = RiskValidationResult(approved=[mock_approved], rejected=[])
    mock_risk_instance = MockRisk.return_value
    mock_risk_instance.validate_trades = MagicMock(return_value=mock_risk_result)

    # MemoryService mock
    mock_memory_instance = MockMemory.return_value
    mock_memory_instance.retrieve_memory = AsyncMock(return_value=[])
    mock_memory_instance.format_memory_for_prompt = MagicMock(return_value=[])

    # ReportGenerator mock
    mock_report_gen_instance = MockReportGen.return_value
    mock_report_gen_instance.generate_reports = AsyncMock(return_value=[MagicMock(id=1)])

    # TradeRepository mock
    MockTradeRepo.create = AsyncMock(return_value=MagicMock())

    broker = _make_broker_adapter()

    session_factory, mock_session = _make_session_factory()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()

    svc = PipelineService(
        session_factory=session_factory,
        settings=settings,
        market_data_adapter=_make_market_data_adapter(tickers),
        llm_adapter=_make_llm_adapter(tickers),
        news_adapter=_make_news_adapter(),
        broker_adapter=broker,
    )

    result = await svc.run()

    assert result.status == PipelineStatus.SUCCESS
    assert result.stocks_analyzed == 2
    assert result.completed_at is not None


@patch("tradeagent.services.pipeline.PortfolioRepository")
@patch("tradeagent.services.pipeline.StockRepository")
@patch("tradeagent.services.pipeline.TechnicalAnalysisService")
@patch("tradeagent.services.pipeline.ScreeningService")
@patch("tradeagent.services.pipeline.RiskManager")
@patch("tradeagent.services.pipeline.MemoryService")
@patch("tradeagent.services.pipeline.ReportGenerator")
async def test_pipeline_no_market_data_aborts(
    MockReportGen,
    MockMemory,
    MockRisk,
    MockScreener,
    MockTA,
    MockStockRepo,
    MockPortfolioRepo,
    settings: Settings,
):
    """Pipeline should FAIL immediately when no stocks are active."""
    MockStockRepo.get_all_active = AsyncMock(return_value=([], 0))
    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[])

    empty_market_adapter = AsyncMock()
    empty_market_adapter.fetch_prices = AsyncMock(return_value={})
    empty_market_adapter.fetch_fundamentals = AsyncMock(return_value={})

    session_factory, mock_session = _make_session_factory()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()

    svc = PipelineService(
        session_factory=session_factory,
        settings=settings,
        market_data_adapter=empty_market_adapter,
        llm_adapter=AsyncMock(),
        news_adapter=AsyncMock(),
        broker_adapter=None,
    )

    result = await svc.run()

    assert result.status == PipelineStatus.FAILED
    assert any("No market data" in e or "market data" in e.lower() for e in result.errors)


@patch("tradeagent.services.pipeline.PortfolioRepository")
@patch("tradeagent.services.pipeline.StockRepository")
@patch("tradeagent.services.pipeline.TradeRepository")
@patch("tradeagent.services.pipeline.ReportGenerator")
@patch("tradeagent.services.pipeline.MemoryService")
@patch("tradeagent.services.pipeline.RiskManager")
@patch("tradeagent.services.pipeline.ScreeningService")
@patch("tradeagent.services.pipeline.TechnicalAnalysisService")
async def test_pipeline_news_failure_continues(
    MockTA,
    MockScreener,
    MockRisk,
    MockMemory,
    MockReportGen,
    MockTradeRepo,
    MockStockRepo,
    MockPortfolioRepo,
    settings: Settings,
):
    """News fetch failure should not abort the pipeline (non-critical)."""
    tickers = ["AAPL"]
    stocks = [_make_stock(1, "AAPL")]

    MockStockRepo.get_all_active = AsyncMock(return_value=(stocks, 1))
    MockStockRepo.bulk_upsert_prices = AsyncMock()
    MockStockRepo.upsert_fundamental = AsyncMock()
    MockStockRepo.update = AsyncMock()
    MockStockRepo.get_latest_price = AsyncMock(return_value=MagicMock(close=Decimal("152.00")))

    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[])
    MockPortfolioRepo.get_open_position_by_stock = AsyncMock(return_value=None)
    MockPortfolioRepo.create_position = AsyncMock(return_value=MagicMock())

    mock_ta_instance = MockTA.return_value
    mock_ta_instance.prices_to_dataframe = MagicMock(return_value=MagicMock())
    mock_ta_instance.compute_indicators = MagicMock(
        return_value={"rsi": 45.0, "macd": {"direction": "neutral"}, "latest_close": 152.0}
    )

    mock_candidate = MagicMock()
    mock_candidate.stock_id = 1
    mock_candidate.ticker = "AAPL"
    mock_candidate.sector = "Technology"
    mock_candidate.total_score = 0.75
    mock_candidate.indicators = {"rsi": 45.0, "macd": {"direction": "neutral"}, "latest_close": 152.0}
    mock_candidate.fundamentals = {}
    mock_candidate.in_portfolio = False
    MockScreener.return_value.score_and_rank = MagicMock(return_value=[mock_candidate])

    from tradeagent.services.risk_manager import RiskValidationResult
    MockRisk.return_value.validate_trades = MagicMock(return_value=RiskValidationResult())

    MockMemory.return_value.retrieve_memory = AsyncMock(return_value=[])
    MockMemory.return_value.format_memory_for_prompt = MagicMock(return_value=[])

    MockReportGen.return_value.generate_reports = AsyncMock(return_value=[])

    # News adapter raises
    failing_news = AsyncMock()
    failing_news.query_news = AsyncMock(side_effect=Exception("News service down"))

    session_factory, mock_session = _make_session_factory()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()

    svc = PipelineService(
        session_factory=session_factory,
        settings=settings,
        market_data_adapter=_make_market_data_adapter(tickers),
        llm_adapter=_make_llm_adapter(tickers),
        news_adapter=failing_news,
        broker_adapter=None,
    )

    result = await svc.run()

    assert result.status in (PipelineStatus.SUCCESS, PipelineStatus.PARTIAL_FAILURE)
    assert result.stocks_analyzed > 0
    # The news error is captured but pipeline continues
    assert any("News fetch failed" in e for e in result.errors)


@patch("tradeagent.services.pipeline.PortfolioRepository")
@patch("tradeagent.services.pipeline.StockRepository")
@patch("tradeagent.services.pipeline.MemoryService")
@patch("tradeagent.services.pipeline.RiskManager")
@patch("tradeagent.services.pipeline.ScreeningService")
@patch("tradeagent.services.pipeline.TechnicalAnalysisService")
async def test_pipeline_llm_failure_aborts(
    MockTA,
    MockScreener,
    MockRisk,
    MockMemory,
    MockStockRepo,
    MockPortfolioRepo,
    settings: Settings,
):
    """LLMError should abort the pipeline with FAILED status."""
    tickers = ["AAPL"]
    stocks = [_make_stock(1, "AAPL")]

    MockStockRepo.get_all_active = AsyncMock(return_value=(stocks, 1))
    MockStockRepo.bulk_upsert_prices = AsyncMock()
    MockStockRepo.upsert_fundamental = AsyncMock()
    MockStockRepo.update = AsyncMock()
    MockStockRepo.get_latest_price = AsyncMock(return_value=MagicMock(close=Decimal("152.00")))

    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[])

    mock_ta_instance = MockTA.return_value
    mock_ta_instance.prices_to_dataframe = MagicMock(return_value=MagicMock())
    mock_ta_instance.compute_indicators = MagicMock(
        return_value={"rsi": 40.0, "macd": {"direction": "bullish"}, "latest_close": 152.0}
    )

    mock_candidate = MagicMock()
    mock_candidate.stock_id = 1
    mock_candidate.ticker = "AAPL"
    mock_candidate.sector = "Technology"
    mock_candidate.total_score = 0.7
    mock_candidate.indicators = {"rsi": 40.0, "macd": {"direction": "bullish"}, "latest_close": 152.0}
    mock_candidate.fundamentals = {}
    mock_candidate.in_portfolio = False
    MockScreener.return_value.score_and_rank = MagicMock(return_value=[mock_candidate])

    MockMemory.return_value.retrieve_memory = AsyncMock(return_value=[])
    MockMemory.return_value.format_memory_for_prompt = MagicMock(return_value=[])

    failing_llm = AsyncMock()
    failing_llm.analyze = AsyncMock(side_effect=LLMError("LLM subprocess timed out"))

    session_factory, mock_session = _make_session_factory()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()

    svc = PipelineService(
        session_factory=session_factory,
        settings=settings,
        market_data_adapter=_make_market_data_adapter(tickers),
        llm_adapter=failing_llm,
        news_adapter=_make_news_adapter(),
        broker_adapter=None,
    )

    result = await svc.run()

    assert result.status == PipelineStatus.FAILED
    assert any("LLM" in e or "timed out" in e for e in result.errors)


@patch("tradeagent.services.pipeline.PortfolioRepository")
@patch("tradeagent.services.pipeline.StockRepository")
@patch("tradeagent.services.pipeline.TradeRepository")
@patch("tradeagent.services.pipeline.ReportGenerator")
@patch("tradeagent.services.pipeline.MemoryService")
@patch("tradeagent.services.pipeline.RiskManager")
@patch("tradeagent.services.pipeline.ScreeningService")
@patch("tradeagent.services.pipeline.TechnicalAnalysisService")
async def test_pipeline_no_broker_skips_execution(
    MockTA,
    MockScreener,
    MockRisk,
    MockMemory,
    MockReportGen,
    MockTradeRepo,
    MockStockRepo,
    MockPortfolioRepo,
    settings: Settings,
):
    """When broker_adapter is None, trades_executed should be 0."""
    tickers = ["AAPL"]
    stocks = [_make_stock(1, "AAPL")]

    MockStockRepo.get_all_active = AsyncMock(return_value=(stocks, 1))
    MockStockRepo.bulk_upsert_prices = AsyncMock()
    MockStockRepo.upsert_fundamental = AsyncMock()
    MockStockRepo.update = AsyncMock()
    MockStockRepo.get_latest_price = AsyncMock(return_value=MagicMock(close=Decimal("152.00")))

    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[])
    MockPortfolioRepo.get_open_position_by_stock = AsyncMock(return_value=None)

    mock_ta_instance = MockTA.return_value
    mock_ta_instance.prices_to_dataframe = MagicMock(return_value=MagicMock())
    mock_ta_instance.compute_indicators = MagicMock(
        return_value={"rsi": 35.0, "macd": {"direction": "bullish", "histogram": 0.5}, "latest_close": 152.0}
    )

    mock_candidate = MagicMock()
    mock_candidate.stock_id = 1
    mock_candidate.ticker = "AAPL"
    mock_candidate.sector = "Technology"
    mock_candidate.total_score = 0.8
    mock_candidate.indicators = {"rsi": 35.0, "macd": {"direction": "bullish", "histogram": 0.5}, "latest_close": 152.0}
    mock_candidate.fundamentals = {}
    mock_candidate.in_portfolio = False
    MockScreener.return_value.score_and_rank = MagicMock(return_value=[mock_candidate])

    from tradeagent.services.risk_manager import ApprovedTrade, RiskValidationResult
    mock_approved = ApprovedTrade(
        ticker="AAPL",
        stock_id=1,
        action="BUY",
        side="BUY",
        quantity=Decimal("5.000000"),
        estimated_value=Decimal("760.00"),
        confidence=0.8,
        reasoning="Strong momentum",
    )
    MockRisk.return_value.validate_trades = MagicMock(
        return_value=RiskValidationResult(approved=[mock_approved], rejected=[])
    )

    MockMemory.return_value.retrieve_memory = AsyncMock(return_value=[])
    MockMemory.return_value.format_memory_for_prompt = MagicMock(return_value=[])

    MockReportGen.return_value.generate_reports = AsyncMock(return_value=[])

    session_factory, mock_session = _make_session_factory()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()

    svc = PipelineService(
        session_factory=session_factory,
        settings=settings,
        market_data_adapter=_make_market_data_adapter(tickers),
        llm_adapter=_make_llm_adapter(tickers),
        news_adapter=_make_news_adapter(),
        broker_adapter=None,  # No broker
    )

    result = await svc.run()

    assert result.trades_executed == 0
