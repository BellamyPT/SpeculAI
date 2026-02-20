"""Trade history API routes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tradeagent.api.dependencies import get_db_session
from tradeagent.repositories.trade import TradeRepository
from tradeagent.schemas.common import PaginatedResponse, PaginationMeta
from tradeagent.schemas.trade import TradeResponse

router = APIRouter()


@router.get("/trades")
async def list_trades(
    session: AsyncSession = Depends(get_db_session),
    ticker: str | None = Query(None),
    side: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    include_backtest: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[TradeResponse]:
    """Return paginated, filtered trade history."""
    trades, total = await TradeRepository.get_history(
        session,
        ticker=ticker,
        side=side,
        start_date=start_date,
        end_date=end_date,
        include_backtest=include_backtest,
        limit=limit,
        offset=offset,
    )

    data = []
    for trade in trades:
        resp = TradeResponse.model_validate(trade)
        resp.ticker = trade.stock.ticker if trade.stock else None
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
