from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class StockResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    ticker: str
    name: str
    exchange: str
    sector: str | None
    industry: str | None
    country: str | None
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StockPriceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    stock_id: int
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adj_close: Decimal
    volume: int


class StockFundamentalResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    stock_id: int
    snapshot_date: date
    market_cap: Decimal | None
    pe_ratio: Decimal | None
    forward_pe: Decimal | None
    peg_ratio: Decimal | None
    price_to_book: Decimal | None
    price_to_sales: Decimal | None
    dividend_yield: Decimal | None
    eps: Decimal | None
    revenue_growth: Decimal | None
    earnings_growth: Decimal | None
    profit_margin: Decimal | None
    debt_to_equity: Decimal | None
    current_ratio: Decimal | None
    beta: Decimal | None
    next_earnings_date: date | None
