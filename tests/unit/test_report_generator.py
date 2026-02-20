"""Unit tests for ReportGenerator."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tradeagent.adapters.base import NewsItem
from tradeagent.core.types import ContextType
from tradeagent.services.memory import MemoryItem
from tradeagent.services.report_generator import ReportGenerator
from tradeagent.services.risk_manager import (
    ApprovedTrade,
    PortfolioState,
    PositionInfo,
    RejectedTrade,
    RiskValidationResult,
)
from tradeagent.services.screening import CandidateScore


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_candidate(stock_id: int, ticker: str) -> CandidateScore:
    return CandidateScore(
        stock_id=stock_id,
        ticker=ticker,
        sector="Technology",
        total_score=0.72,
        component_scores={"rsi": 0.8, "macd": 1.0},
        indicators={"rsi": 40.0, "macd": {"direction": "bullish"}, "latest_close": 152.0},
        fundamentals={"market_cap": 3_000_000_000_000, "pe_ratio": 28.5},
        in_portfolio=False,
    )


def _make_approved(stock_id: int, ticker: str) -> ApprovedTrade:
    return ApprovedTrade(
        ticker=ticker,
        stock_id=stock_id,
        action="BUY",
        side="BUY",
        quantity=Decimal("5.000000"),
        estimated_value=Decimal("760.00"),
        confidence=0.8,
        reasoning="Strong technical signals",
    )


def _make_rejected(stock_id: int, ticker: str) -> RejectedTrade:
    return RejectedTrade(
        ticker=ticker,
        stock_id=stock_id,
        action="BUY",
        confidence=0.6,
        rejection_reason="Insufficient cash",
    )


def _make_news_item() -> NewsItem:
    return NewsItem(
        source="Bloomberg",
        headline="Tech stocks surge",
        summary="Technology companies post strong earnings",
        published_at=datetime.now(tz=timezone.utc),
        url="https://bloomberg.com/tech",
        relevance_score=0.85,
    )


def _make_memory_item(stock_id: int, ticker: str) -> MemoryItem:
    return MemoryItem(
        decision_id=42,
        ticker=ticker,
        action="BUY",
        confidence=0.75,
        reasoning_snippet="Previous buy based on oversold RSI conditions",
        outcome_pnl=0.035,
        outcome_assessed=True,
        decision_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        retrieval_strategy="ticker",
    )


def _make_portfolio_state() -> PortfolioState:
    return PortfolioState(
        total_value=Decimal("50000.00"),
        cash_available=Decimal("48000.00"),
        positions={},
        num_open_positions=0,
    )


def _make_mock_session() -> AsyncMock:
    return AsyncMock()


def _make_mock_report(report_id: int) -> MagicMock:
    report = MagicMock()
    report.id = report_id
    return report


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("tradeagent.services.report_generator.DecisionRepository")
async def test_reports_for_all_recommendations(MockDecisionRepo):
    """One approved + one rejected trade should produce two DecisionReport rows."""
    pipeline_run_id = uuid4()
    session = _make_mock_session()

    approved = _make_approved(1, "AAPL")
    rejected = _make_rejected(2, "MSFT")
    risk_result = RiskValidationResult(approved=[approved], rejected=[rejected])
    candidates = [_make_candidate(1, "AAPL"), _make_candidate(2, "MSFT")]
    portfolio_state = _make_portfolio_state()

    # Each call to DecisionRepository.create returns a unique mock report
    report_calls = [_make_mock_report(1), _make_mock_report(2)]
    MockDecisionRepo.create = AsyncMock(side_effect=report_calls)
    MockDecisionRepo.bulk_create_context_items = AsyncMock(return_value=[])

    gen = ReportGenerator()
    reports = await gen.generate_reports(
        session=session,
        pipeline_run_id=pipeline_run_id,
        candidates=candidates,
        risk_result=risk_result,
        news=[],
        memory={},
        portfolio_state=portfolio_state,
    )

    assert len(reports) == 2
    assert MockDecisionRepo.create.call_count == 2


@patch("tradeagent.services.report_generator.DecisionRepository")
async def test_context_items_created(MockDecisionRepo):
    """Context items should include TECHNICAL, NEWS, and MEMORY types."""
    pipeline_run_id = uuid4()
    session = _make_mock_session()

    approved = _make_approved(1, "AAPL")
    risk_result = RiskValidationResult(approved=[approved], rejected=[])
    candidates = [_make_candidate(1, "AAPL")]
    portfolio_state = _make_portfolio_state()
    news = [_make_news_item()]
    memory_item = _make_memory_item(1, "AAPL")
    memory = {1: [memory_item]}

    mock_report = _make_mock_report(10)
    MockDecisionRepo.create = AsyncMock(return_value=mock_report)
    MockDecisionRepo.bulk_create_context_items = AsyncMock(return_value=[])

    gen = ReportGenerator()
    await gen.generate_reports(
        session=session,
        pipeline_run_id=pipeline_run_id,
        candidates=candidates,
        risk_result=risk_result,
        news=news,
        memory=memory,
        portfolio_state=portfolio_state,
    )

    assert MockDecisionRepo.bulk_create_context_items.called
    call_args = MockDecisionRepo.bulk_create_context_items.call_args
    items = call_args[0][1]  # second positional arg is the items list

    context_types = {item["context_type"] for item in items}
    assert ContextType.TECHNICAL in context_types
    assert ContextType.NEWS in context_types
    assert ContextType.MEMORY in context_types


@patch("tradeagent.services.report_generator.DecisionRepository")
async def test_empty_news_and_memory(MockDecisionRepo):
    """Empty news + empty memory dict should still create reports with TECHNICAL context only."""
    pipeline_run_id = uuid4()
    session = _make_mock_session()

    approved = _make_approved(1, "AAPL")
    risk_result = RiskValidationResult(approved=[approved], rejected=[])
    candidates = [_make_candidate(1, "AAPL")]
    portfolio_state = _make_portfolio_state()

    mock_report = _make_mock_report(5)
    MockDecisionRepo.create = AsyncMock(return_value=mock_report)
    MockDecisionRepo.bulk_create_context_items = AsyncMock(return_value=[])

    gen = ReportGenerator()
    reports = await gen.generate_reports(
        session=session,
        pipeline_run_id=pipeline_run_id,
        candidates=candidates,
        risk_result=risk_result,
        news=[],
        memory={},
        portfolio_state=portfolio_state,
    )

    assert len(reports) == 1
    assert MockDecisionRepo.create.call_count == 1

    # Context items should still be created (at least TECHNICAL)
    assert MockDecisionRepo.bulk_create_context_items.called
    call_args = MockDecisionRepo.bulk_create_context_items.call_args
    items = call_args[0][1]
    context_types = {item["context_type"] for item in items}
    assert ContextType.TECHNICAL in context_types
    assert ContextType.NEWS not in context_types
    assert ContextType.MEMORY not in context_types


@patch("tradeagent.services.report_generator.DecisionRepository")
async def test_rejected_trade_reasoning_prefixed(MockDecisionRepo):
    """Rejected trades should have 'REJECTED: ' prefix in their reasoning."""
    pipeline_run_id = uuid4()
    session = _make_mock_session()

    rejected = _make_rejected(1, "AAPL")
    risk_result = RiskValidationResult(approved=[], rejected=[rejected])
    candidates = [_make_candidate(1, "AAPL")]
    portfolio_state = _make_portfolio_state()

    mock_report = _make_mock_report(7)
    MockDecisionRepo.create = AsyncMock(return_value=mock_report)
    MockDecisionRepo.bulk_create_context_items = AsyncMock(return_value=[])

    gen = ReportGenerator()
    await gen.generate_reports(
        session=session,
        pipeline_run_id=pipeline_run_id,
        candidates=candidates,
        risk_result=risk_result,
        news=[],
        memory={},
        portfolio_state=portfolio_state,
    )

    create_call_kwargs = MockDecisionRepo.create.call_args[1]
    assert create_call_kwargs["reasoning"].startswith("REJECTED:")


@patch("tradeagent.services.report_generator.DecisionRepository")
async def test_no_context_items_when_no_candidate(MockDecisionRepo):
    """If a stock has no candidate, context items should not be created via bulk_create."""
    pipeline_run_id = uuid4()
    session = _make_mock_session()

    # Approved trade but no matching candidate
    approved = _make_approved(99, "UNKNOWN")
    risk_result = RiskValidationResult(approved=[approved], rejected=[])
    candidates = []  # No candidates
    portfolio_state = _make_portfolio_state()

    mock_report = _make_mock_report(3)
    MockDecisionRepo.create = AsyncMock(return_value=mock_report)
    MockDecisionRepo.bulk_create_context_items = AsyncMock(return_value=[])

    gen = ReportGenerator()
    await gen.generate_reports(
        session=session,
        pipeline_run_id=pipeline_run_id,
        candidates=candidates,
        risk_result=risk_result,
        news=[],
        memory={},
        portfolio_state=portfolio_state,
    )

    # bulk_create_context_items should not be called (no items to create)
    # OR called with empty list — both are acceptable
    if MockDecisionRepo.bulk_create_context_items.called:
        call_args = MockDecisionRepo.bulk_create_context_items.call_args
        items = call_args[0][1]
        assert items == []
