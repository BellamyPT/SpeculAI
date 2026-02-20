"""Pipeline schemas for API responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PipelineRunInfo(BaseModel):
    pipeline_run_id: UUID
    status: str
    started_at: datetime
    completed_at: datetime | None
    stocks_analyzed: int
    candidates_screened: int
    trades_approved: int
    trades_executed: int
    errors: list[str]


class PipelineStatusResponse(BaseModel):
    status: str | None
    last_run: PipelineRunInfo | None = None


class PipelineTriggerResponse(BaseModel):
    message: str
    pipeline_run_id: UUID | None = None
