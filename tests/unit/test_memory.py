"""Tests for the MemoryService."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tradeagent.config import MemoryConfig
from tradeagent.services.memory import MemoryItem, MemoryService


@pytest.fixture
def config() -> MemoryConfig:
    return MemoryConfig(
        max_items_per_candidate=10,
        exact_ticker_max=10,
        sector_max=5,
        outcome_lookback_days=7,
    )


@pytest.fixture
def service(config: MemoryConfig) -> MemoryService:
    return MemoryService(config)


def _mock_report(
    report_id: int = 1,
    ticker: str = "AAPL",
    action: str = "BUY",
    confidence: float = 0.8,
    reasoning: str = "Strong technical signals indicate upward momentum",
    outcome_pnl: float | None = None,
    outcome_assessed_at: datetime | None = None,
) -> MagicMock:
    report = MagicMock()
    report.id = report_id
    report.action = action
    report.confidence = Decimal(str(confidence))
    report.reasoning = reasoning
    report.outcome_pnl = Decimal(str(outcome_pnl)) if outcome_pnl is not None else None
    report.outcome_assessed_at = outcome_assessed_at
    report.created_at = datetime(2024, 6, 15, tzinfo=timezone.utc)
    report.technical_summary = {"rsi": 45.0, "latest_close": 150.0}

    # Stock relationship
    stock = MagicMock()
    stock.ticker = ticker
    report.stock = stock
    return report


class TestRetrieveMemory:
    async def test_ticker_retrieval(self, service):
        session = AsyncMock()
        report = _mock_report(report_id=1)

        with patch(
            "tradeagent.services.memory.DecisionRepository.get_by_ticker",
            new_callable=AsyncMock,
            return_value=[report],
        ):
            with patch(
                "tradeagent.services.memory.DecisionRepository.get_by_sector",
                new_callable=AsyncMock,
                return_value=[],
            ):
                with patch(
                    "tradeagent.services.memory.DecisionRepository.get_by_similar_signals",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    items = await service.retrieve_memory(
                        session, stock_id=1, ticker="AAPL", sector="Technology",
                        rsi_value=45.0, macd_direction="bullish",
                    )

        assert len(items) == 1
        assert items[0].ticker == "AAPL"
        assert items[0].retrieval_strategy == "ticker"

    async def test_sector_retrieval(self, service):
        session = AsyncMock()
        report = _mock_report(report_id=2, ticker="MSFT")

        with patch(
            "tradeagent.services.memory.DecisionRepository.get_by_ticker",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with patch(
                "tradeagent.services.memory.DecisionRepository.get_by_sector",
                new_callable=AsyncMock,
                return_value=[report],
            ):
                with patch(
                    "tradeagent.services.memory.DecisionRepository.get_by_similar_signals",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    items = await service.retrieve_memory(
                        session, stock_id=1, ticker="AAPL", sector="Technology",
                        rsi_value=None, macd_direction=None,
                    )

        assert len(items) == 1
        assert items[0].ticker == "MSFT"
        assert items[0].retrieval_strategy == "sector"

    async def test_deduplication(self, service):
        """Same report from multiple strategies is deduplicated."""
        session = AsyncMock()
        report = _mock_report(report_id=1)

        with patch(
            "tradeagent.services.memory.DecisionRepository.get_by_ticker",
            new_callable=AsyncMock,
            return_value=[report],
        ):
            with patch(
                "tradeagent.services.memory.DecisionRepository.get_by_sector",
                new_callable=AsyncMock,
                return_value=[report],  # same report
            ):
                with patch(
                    "tradeagent.services.memory.DecisionRepository.get_by_similar_signals",
                    new_callable=AsyncMock,
                    return_value=[report],  # same report again
                ):
                    items = await service.retrieve_memory(
                        session, stock_id=1, ticker="AAPL", sector="Technology",
                        rsi_value=45.0, macd_direction="bullish",
                    )

        assert len(items) == 1

    async def test_max_items_cap(self):
        config = MemoryConfig(max_items_per_candidate=3)
        svc = MemoryService(config)
        session = AsyncMock()
        reports = [_mock_report(report_id=i) for i in range(10)]

        with patch(
            "tradeagent.services.memory.DecisionRepository.get_by_ticker",
            new_callable=AsyncMock,
            return_value=reports,
        ):
            with patch(
                "tradeagent.services.memory.DecisionRepository.get_by_sector",
                new_callable=AsyncMock,
                return_value=[],
            ):
                with patch(
                    "tradeagent.services.memory.DecisionRepository.get_by_similar_signals",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    items = await svc.retrieve_memory(
                        session, stock_id=1, ticker="AAPL", sector=None,
                        rsi_value=None, macd_direction=None,
                    )

        assert len(items) == 3

    async def test_empty_history(self, service):
        session = AsyncMock()

        with patch(
            "tradeagent.services.memory.DecisionRepository.get_by_ticker",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with patch(
                "tradeagent.services.memory.DecisionRepository.get_by_sector",
                new_callable=AsyncMock,
                return_value=[],
            ):
                with patch(
                    "tradeagent.services.memory.DecisionRepository.get_by_similar_signals",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    items = await service.retrieve_memory(
                        session, stock_id=1, ticker="AAPL", sector="Technology",
                        rsi_value=45.0, macd_direction="bullish",
                    )

        assert items == []

    async def test_no_sector_skips_sector_query(self, service):
        session = AsyncMock()

        with patch(
            "tradeagent.services.memory.DecisionRepository.get_by_ticker",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_ticker:
            with patch(
                "tradeagent.services.memory.DecisionRepository.get_by_sector",
                new_callable=AsyncMock,
            ) as mock_sector:
                with patch(
                    "tradeagent.services.memory.DecisionRepository.get_by_similar_signals",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    await service.retrieve_memory(
                        session, stock_id=1, ticker="AAPL", sector=None,
                        rsi_value=None, macd_direction=None,
                    )

        mock_ticker.assert_called_once()
        mock_sector.assert_not_called()


class TestReasoningTruncation:
    def test_long_reasoning_truncated(self):
        long_text = "A" * 300
        report = _mock_report(reasoning=long_text)
        item = MemoryService._report_to_item(report, "ticker")
        assert len(item.reasoning_snippet) == 200

    def test_short_reasoning_not_truncated(self):
        report = _mock_report(reasoning="Short.")
        item = MemoryService._report_to_item(report, "ticker")
        assert item.reasoning_snippet == "Short."


class TestFormatMemoryForPrompt:
    def test_formats_items(self, service):
        items = [
            MemoryItem(
                decision_id=1,
                ticker="AAPL",
                action="BUY",
                confidence=0.8,
                reasoning_snippet="RSI oversold",
                outcome_pnl=0.05,
                outcome_assessed=True,
                decision_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
                retrieval_strategy="ticker",
            )
        ]
        formatted = service.format_memory_for_prompt(items)
        assert len(formatted) == 1
        assert formatted[0]["ticker"] == "AAPL"
        assert formatted[0]["outcome_pnl"] == 0.05


class TestAssessOutcomes:
    async def test_assess_unassessed(self, service):
        session = AsyncMock()
        report = _mock_report(report_id=1)

        with patch(
            "tradeagent.services.memory.DecisionRepository.get_unassessed",
            new_callable=AsyncMock,
            return_value=[report],
        ):
            with patch(
                "tradeagent.services.memory.DecisionRepository.update_outcome",
                new_callable=AsyncMock,
            ) as mock_update:
                count = await service.assess_outcomes(session)

        assert count == 1
        mock_update.assert_called_once()

    async def test_assess_no_reports(self, service):
        session = AsyncMock()

        with patch(
            "tradeagent.services.memory.DecisionRepository.get_unassessed",
            new_callable=AsyncMock,
            return_value=[],
        ):
            count = await service.assess_outcomes(session)

        assert count == 0
