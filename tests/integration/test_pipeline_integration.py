"""Integration test: pipeline with all mock adapters end-to-end."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from tradeagent.adapters.base import (
    LLMResponse,
    NewsItem,
    PriceBar,
    ValidationResult,
)
from tradeagent.config import Settings
from tradeagent.core.types import PipelineStatus
from tradeagent.services.pipeline import PipelineService


def _make_session_factory():
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory.return_value = mock_session_ctx
    return mock_session_factory, mock_session


def _make_stock(stock_id: int, ticker: str, sector: str = "Technology"):
    stock = MagicMock()
    stock.id = stock_id
    stock.ticker = ticker
    stock.sector = sector
    stock.name = f"{ticker} Inc."
    stock.industry = "Software"
    return stock


@patch("tradeagent.services.pipeline.PortfolioRepository")
@patch("tradeagent.services.pipeline.StockRepository")
@patch("tradeagent.services.pipeline.TradeRepository")
@patch("tradeagent.services.pipeline.ReportGenerator")
@patch("tradeagent.services.pipeline.MemoryService")
@patch("tradeagent.services.pipeline.RiskManager")
@patch("tradeagent.services.pipeline.ScreeningService")
@patch("tradeagent.services.pipeline.TechnicalAnalysisService")
async def test_full_pipeline_with_mock_adapters(
    MockTA,
    MockScreener,
    MockRisk,
    MockMemory,
    MockReportGen,
    MockTradeRepo,
    MockStockRepo,
    MockPortfolioRepo,
):
    """End-to-end pipeline run using mock LLM, market data, news, and broker adapters."""
    from tradeagent.adapters.broker.mock_broker import MockBrokerAdapter
    from tradeagent.adapters.llm.mock_llm import MockLLMAdapter
    from tradeagent.adapters.market_data.mock_market_data import MockMarketDataAdapter
    from tradeagent.adapters.news.mock_news import MockNewsAdapter
    from tradeagent.services.risk_manager import ApprovedTrade, RiskValidationResult

    settings = Settings()
    tickers = ["AAPL", "MSFT"]
    stocks = [_make_stock(1, "AAPL"), _make_stock(2, "MSFT")]

    # StockRepository
    MockStockRepo.get_all_active = AsyncMock(return_value=(stocks, 2))
    MockStockRepo.bulk_upsert_prices = AsyncMock()
    MockStockRepo.upsert_fundamental = AsyncMock()
    MockStockRepo.update = AsyncMock()
    MockStockRepo.get_latest_price = AsyncMock(return_value=MagicMock(close=Decimal("152.00")))

    # PortfolioRepository
    MockPortfolioRepo.get_open_positions = AsyncMock(return_value=[])
    MockPortfolioRepo.get_open_position_by_stock = AsyncMock(return_value=None)
    MockPortfolioRepo.create_position = AsyncMock(return_value=MagicMock())

    # TechnicalAnalysis
    mock_ta = MockTA.return_value
    mock_ta.prices_to_dataframe = MagicMock(return_value=MagicMock())
    mock_ta.compute_indicators = MagicMock(
        return_value={"rsi": 35.0, "macd": {"direction": "bullish", "histogram": 0.5}, "latest_close": 152.0}
    )

    # Screening
    mock_candidate = MagicMock()
    mock_candidate.stock_id = 1
    mock_candidate.ticker = "AAPL"
    mock_candidate.sector = "Technology"
    mock_candidate.total_score = 0.8
    mock_candidate.indicators = {"rsi": 35.0, "macd": {"direction": "bullish", "histogram": 0.5}, "latest_close": 152.0}
    mock_candidate.fundamentals = {"market_cap": 3_000_000_000_000}
    mock_candidate.in_portfolio = False
    MockScreener.return_value.score_and_rank = MagicMock(return_value=[mock_candidate])

    # Risk
    approved = ApprovedTrade(
        ticker="AAPL", stock_id=1, action="BUY", side="BUY",
        quantity=Decimal("5"), estimated_value=Decimal("760"),
        confidence=0.8, reasoning="Strong momentum",
    )
    MockRisk.return_value.validate_trades = MagicMock(
        return_value=RiskValidationResult(approved=[approved], rejected=[])
    )

    # Memory
    MockMemory.return_value.retrieve_memory = AsyncMock(return_value=[])
    MockMemory.return_value.format_memory_for_prompt = MagicMock(return_value=[])

    # Reports
    MockReportGen.return_value.generate_reports = AsyncMock(return_value=[MagicMock(id=1)])

    # Trade repo
    MockTradeRepo.create = AsyncMock(return_value=MagicMock())

    # Mock adapters
    market_data = MockMarketDataAdapter()
    market_data.load_prices({
        t: [PriceBar(
            ticker=t, date=date(2024, 1, 2),
            open=Decimal("150"), high=Decimal("155"), low=Decimal("148"),
            close=Decimal("152"), adj_close=Decimal("152"), volume=1_000_000,
        )] for t in tickers
    })

    llm = MockLLMAdapter()
    news = MockNewsAdapter()
    broker = MockBrokerAdapter()
    broker.set_current_price("AAPL", Decimal("152.00"))

    session_factory, _ = _make_session_factory()

    svc = PipelineService(
        session_factory=session_factory,
        settings=settings,
        market_data_adapter=market_data,
        llm_adapter=llm,
        news_adapter=news,
        broker_adapter=broker,
    )

    result = await svc.run()

    assert result.status == PipelineStatus.SUCCESS
    assert result.stocks_analyzed == 2
    assert result.trades_approved > 0
    assert result.completed_at is not None
