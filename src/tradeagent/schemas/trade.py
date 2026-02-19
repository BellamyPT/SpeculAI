from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class TradeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    stock_id: int
    decision_report_id: int | None
    side: str
    quantity: Decimal
    price: Decimal
    total_value: Decimal
    currency: str
    broker_order_id: str | None
    status: str
    executed_at: datetime | None
    is_backtest: bool
    backtest_run_id: UUID | None
    created_at: datetime
