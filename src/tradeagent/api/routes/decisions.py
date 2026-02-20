"""Decision report API routes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from tradeagent.api.dependencies import get_db_session
from tradeagent.repositories.decision import DecisionRepository
from tradeagent.schemas.common import PaginatedResponse, PaginationMeta
from tradeagent.schemas.decision import DecisionReportDetailResponse, DecisionReportResponse

router = APIRouter()


@router.get("/decisions")
async def list_decisions(
    session: AsyncSession = Depends(get_db_session),
    ticker: str | None = Query(None),
    action: str | None = Query(None),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    include_backtest: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[DecisionReportResponse]:
    """Return paginated, filtered decision reports."""
    reports, total = await DecisionRepository.get_list(
        session,
        ticker=ticker,
        action=action,
        min_confidence=min_confidence,
        start_date=start_date,
        end_date=end_date,
        include_backtest=include_backtest,
        limit=limit,
        offset=offset,
    )

    data = []
    for report in reports:
        resp = DecisionReportResponse.model_validate(report)
        resp.ticker = report.stock.ticker if report.stock else None
        data.append(resp)

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
        ),
    )


@router.get("/decisions/{decision_id}", response_model=None)
async def get_decision_detail(
    decision_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> DecisionReportDetailResponse | JSONResponse:
    """Return full decision report detail with context items."""
    report = await DecisionRepository.get_by_id(session, decision_id)
    if report is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Decision report {decision_id} not found",
                }
            },
        )

    resp = DecisionReportDetailResponse.model_validate(report)
    return resp
