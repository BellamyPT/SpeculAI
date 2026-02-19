from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from tradeagent.api.dependencies import get_db_session
from tradeagent.models.decision import DecisionReport

router = APIRouter()


@router.get("/health")
async def health_check(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return application health status including database connectivity."""
    status = "ok"
    database = "connected"
    last_pipeline_run: str | None = None
    last_pipeline_status: str | None = None

    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        status = "degraded"
        database = "disconnected"

    if database == "connected":
        try:
            result = await session.execute(
                select(DecisionReport)
                .order_by(DecisionReport.created_at.desc())
                .limit(1)
            )
            latest = result.scalar_one_or_none()
            if latest is not None:
                last_pipeline_run = latest.created_at.isoformat()
                last_pipeline_status = latest.action
        except Exception:
            pass

    return {
        "status": status,
        "database": database,
        "last_pipeline_run": last_pipeline_run,
        "last_pipeline_status": last_pipeline_status,
    }
