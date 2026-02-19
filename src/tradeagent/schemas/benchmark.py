from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class BenchmarkResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    symbol: str
    name: str


class BenchmarkPriceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    benchmark_id: int
    date: date
    close: Decimal
