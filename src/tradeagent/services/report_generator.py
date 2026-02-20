"""Report generator — creates decision reports and context items from pipeline results."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tradeagent.adapters.base import NewsItem
from tradeagent.core.logging import get_logger
from tradeagent.core.types import ContextType
from tradeagent.models.decision import DecisionReport
from tradeagent.repositories.decision import DecisionRepository
from tradeagent.services.memory import MemoryItem
from tradeagent.services.risk_manager import (
    ApprovedTrade,
    PortfolioState,
    RejectedTrade,
    RiskValidationResult,
)
from tradeagent.services.screening import CandidateScore

log = get_logger(__name__)


class ReportGenerator:
    """Generate decision reports and context items for each pipeline recommendation."""

    async def generate_reports(
        self,
        session: AsyncSession,
        pipeline_run_id: UUID,
        candidates: list[CandidateScore],
        risk_result: RiskValidationResult,
        news: list[NewsItem],
        memory: dict[int, list[MemoryItem]],
        portfolio_state: PortfolioState,
    ) -> list[DecisionReport]:
        """Create DecisionReport + context items for all approved and rejected trades."""
        reports: list[DecisionReport] = []
        candidate_by_stock_id = {c.stock_id: c for c in candidates}

        portfolio_dict = {
            "total_value": str(portfolio_state.total_value),
            "cash_available": str(portfolio_state.cash_available),
            "num_positions": portfolio_state.num_open_positions,
        }

        # Reports for approved trades
        for trade in risk_result.approved:
            candidate = candidate_by_stock_id.get(trade.stock_id)
            report = await self._create_report(
                session=session,
                pipeline_run_id=pipeline_run_id,
                stock_id=trade.stock_id,
                action=trade.action,
                confidence=trade.confidence,
                reasoning=trade.reasoning,
                candidate=candidate,
                portfolio_dict=portfolio_dict,
            )
            reports.append(report)

            # Create context items
            await self._create_context_items(
                session=session,
                report_id=report.id,
                candidate=candidate,
                news=news,
                memory_items=memory.get(trade.stock_id, []),
            )

        # Reports for rejected trades
        for rejected in risk_result.rejected:
            candidate = candidate_by_stock_id.get(rejected.stock_id)
            reasoning = f"REJECTED: {rejected.rejection_reason}"
            report = await self._create_report(
                session=session,
                pipeline_run_id=pipeline_run_id,
                stock_id=rejected.stock_id,
                action=rejected.action,
                confidence=rejected.confidence,
                reasoning=reasoning,
                candidate=candidate,
                portfolio_dict=portfolio_dict,
            )
            reports.append(report)

            await self._create_context_items(
                session=session,
                report_id=report.id,
                candidate=candidate,
                news=news,
                memory_items=memory.get(rejected.stock_id, []),
            )

        log.info(
            "reports_generated",
            pipeline_run_id=str(pipeline_run_id),
            approved_count=len(risk_result.approved),
            rejected_count=len(risk_result.rejected),
            total_reports=len(reports),
        )
        return reports

    async def _create_report(
        self,
        session: AsyncSession,
        pipeline_run_id: UUID,
        stock_id: int,
        action: str,
        confidence: float,
        reasoning: str,
        candidate: CandidateScore | None,
        portfolio_dict: dict,
    ) -> DecisionReport:
        technical_summary = candidate.indicators if candidate else {}
        news_summary: dict = {}
        memory_refs: dict | None = None

        if candidate:
            news_summary = {"candidate_score": candidate.total_score}

        return await DecisionRepository.create(
            session,
            stock_id=stock_id,
            pipeline_run_id=pipeline_run_id,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            technical_summary=technical_summary,
            news_summary=news_summary,
            portfolio_state=portfolio_dict,
            memory_references=memory_refs,
        )

    async def _create_context_items(
        self,
        session: AsyncSession,
        report_id: int,
        candidate: CandidateScore | None,
        news: list[NewsItem],
        memory_items: list[MemoryItem],
    ) -> None:
        items: list[dict] = []

        # Technical context
        if candidate:
            items.append({
                "decision_report_id": report_id,
                "context_type": ContextType.TECHNICAL,
                "source": f"indicators:{candidate.ticker}",
                "content": json.dumps(candidate.indicators, default=str),
            })

            # Fundamental context
            if candidate.fundamentals:
                items.append({
                    "decision_report_id": report_id,
                    "context_type": ContextType.FUNDAMENTAL,
                    "source": f"fundamentals:{candidate.ticker}",
                    "content": json.dumps(candidate.fundamentals, default=str),
                })

        # News context
        for news_item in news:
            items.append({
                "decision_report_id": report_id,
                "context_type": ContextType.NEWS,
                "source": news_item.source or news_item.url,
                "content": f"{news_item.headline}: {news_item.summary}",
                "relevance_score": news_item.relevance_score,
            })

        # Memory context
        for mem in memory_items:
            items.append({
                "decision_report_id": report_id,
                "context_type": ContextType.MEMORY,
                "source": f"decision:{mem.decision_id}",
                "content": (
                    f"{mem.ticker} {mem.action} (conf: {mem.confidence}, "
                    f"outcome: {mem.outcome_pnl}): {mem.reasoning_snippet}"
                ),
            })

        if items:
            await DecisionRepository.bulk_create_context_items(session, items)
