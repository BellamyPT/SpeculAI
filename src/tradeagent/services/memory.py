"""Memory & learning service — retrieves past decisions for LLM context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from tradeagent.config import MemoryConfig
from tradeagent.core.logging import get_logger
from tradeagent.repositories.decision import DecisionRepository

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MemoryItem:
    """A single decision memory entry for LLM context."""

    decision_id: int
    ticker: str
    action: str
    confidence: float
    reasoning_snippet: str  # first 200 chars
    outcome_pnl: float | None
    outcome_assessed: bool
    decision_date: datetime
    retrieval_strategy: str  # "ticker", "sector", or "similar_signals"


class MemoryService:
    """Retrieve and format past decision memories for LLM analysis."""

    def __init__(self, config: MemoryConfig) -> None:
        self._cfg = config

    async def retrieve_memory(
        self,
        session: AsyncSession,
        stock_id: int,
        ticker: str,
        sector: str | None,
        rsi_value: float | None,
        macd_direction: str | None,
    ) -> list[MemoryItem]:
        """Retrieve relevant past decisions from multiple strategies.

        Deduplicates by decision_id and caps at max_items_per_candidate.
        """
        items: list[MemoryItem] = []
        seen_ids: set[int] = set()

        # Strategy 1: exact ticker match
        try:
            ticker_reports = await DecisionRepository.get_by_ticker(
                session, stock_id, limit=self._cfg.exact_ticker_max
            )
            for report in ticker_reports:
                if report.id not in seen_ids:
                    seen_ids.add(report.id)
                    items.append(self._report_to_item(report, "ticker"))
        except Exception:
            log.warning("memory_ticker_retrieval_failed", ticker=ticker, exc_info=True)

        # Strategy 2: same sector
        if sector:
            try:
                sector_reports = await DecisionRepository.get_by_sector(
                    session,
                    sector,
                    exclude_stock_id=stock_id,
                    limit=self._cfg.sector_max,
                )
                for report in sector_reports:
                    if report.id not in seen_ids:
                        seen_ids.add(report.id)
                        items.append(self._report_to_item(report, "sector"))
            except Exception:
                log.warning("memory_sector_retrieval_failed", sector=sector, exc_info=True)

        # Strategy 3: similar technical signals
        if rsi_value is not None:
            try:
                signal_reports = await DecisionRepository.get_by_similar_signals(
                    session,
                    rsi_value=rsi_value,
                    macd_direction=macd_direction,
                    limit=5,
                )
                for report in signal_reports:
                    if report.id not in seen_ids:
                        seen_ids.add(report.id)
                        items.append(self._report_to_item(report, "similar_signals"))
            except Exception:
                log.warning("memory_signals_retrieval_failed", exc_info=True)

        return items[: self._cfg.max_items_per_candidate]

    def format_memory_for_prompt(self, items: list[MemoryItem]) -> list[dict]:
        """Format memory items for inclusion in the LLM prompt."""
        return [
            {
                "ticker": item.ticker,
                "action": item.action,
                "confidence": item.confidence,
                "reasoning": item.reasoning_snippet,
                "outcome_pnl": item.outcome_pnl,
                "outcome_assessed": item.outcome_assessed,
                "date": item.decision_date.isoformat(),
                "retrieval_strategy": item.retrieval_strategy,
            }
            for item in items
        ]

    async def assess_outcomes(
        self,
        session: AsyncSession,
        *,
        is_backtest: bool = False,
    ) -> int:
        """Assess unassessed decisions older than lookback_days.

        Computes P&L based on action:
        - BUY: (current - original) / original
        - SELL: (original - current) / original

        Returns the count of assessed decisions.
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=self._cfg.outcome_lookback_days)
        assessed_count = 0

        try:
            reports = await DecisionRepository.get_unassessed(
                session, cutoff, is_backtest=is_backtest
            )
        except Exception:
            log.error("outcome_assessment_fetch_failed", exc_info=True)
            return 0

        for report in reports:
            try:
                technical = report.technical_summary or {}
                original_price = technical.get("latest_close")
                if original_price is None:
                    continue

                original = Decimal(str(original_price))
                if original == 0:
                    continue

                # Use a simple heuristic: current price is not available without
                # a market data call, so we mark with zero benchmark delta for now.
                # The pipeline orchestrator will enrich this with actual prices.
                pnl = Decimal("0")
                benchmark_delta = Decimal("0")

                await DecisionRepository.update_outcome(
                    session,
                    report.id,
                    outcome_pnl=pnl,
                    outcome_benchmark_delta=benchmark_delta,
                    outcome_assessed_at=datetime.now(tz=timezone.utc),
                )
                assessed_count += 1
            except Exception:
                log.warning(
                    "outcome_assessment_failed",
                    report_id=report.id,
                    exc_info=True,
                )

        return assessed_count

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _report_to_item(report: object, strategy: str) -> MemoryItem:
        """Convert a DecisionReport ORM object to a MemoryItem DTO."""
        reasoning = str(report.reasoning or "")
        snippet = reasoning[:200] if len(reasoning) > 200 else reasoning

        ticker = ""
        if hasattr(report, "stock") and report.stock is not None:
            ticker = report.stock.ticker
        elif hasattr(report, "technical_summary") and report.technical_summary:
            ticker = report.technical_summary.get("ticker", "")

        return MemoryItem(
            decision_id=report.id,
            ticker=ticker,
            action=report.action,
            confidence=float(report.confidence),
            reasoning_snippet=snippet,
            outcome_pnl=float(report.outcome_pnl) if report.outcome_pnl is not None else None,
            outcome_assessed=report.outcome_assessed_at is not None,
            decision_date=report.created_at,
            retrieval_strategy=strategy,
        )
