"""Pipeline API routes — trigger and status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from tradeagent.core.types import PipelineStatus
from tradeagent.schemas.pipeline import (
    PipelineRunInfo,
    PipelineStatusResponse,
    PipelineTriggerResponse,
)

router = APIRouter()


async def _run_pipeline(app_state) -> None:
    """Background task that runs the pipeline and updates app state."""
    try:
        result = await app_state.pipeline_service.run()
        app_state.pipeline_status = result.status
        app_state.last_pipeline_run = result
    except Exception:
        app_state.pipeline_status = PipelineStatus.FAILED


@router.post("/pipeline/run", status_code=202, response_model=None)
async def trigger_pipeline(
    request: Request,
    background_tasks: BackgroundTasks,
) -> PipelineTriggerResponse | JSONResponse:
    """Manually trigger a pipeline run. Returns 202 Accepted or 409 if already running."""
    app_state = request.app.state

    if getattr(app_state, "pipeline_status", None) == PipelineStatus.RUNNING:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "PIPELINE_ALREADY_RUNNING",
                    "message": "A pipeline run is already in progress",
                }
            },
        )

    app_state.pipeline_status = PipelineStatus.RUNNING
    background_tasks.add_task(_run_pipeline, app_state)

    return PipelineTriggerResponse(message="Pipeline run started")


@router.get("/pipeline/status")
async def pipeline_status(request: Request) -> PipelineStatusResponse:
    """Return current pipeline status and last run info."""
    app_state = request.app.state

    last_run = getattr(app_state, "last_pipeline_run", None)
    last_run_info = None
    if last_run is not None:
        last_run_info = PipelineRunInfo(
            pipeline_run_id=last_run.pipeline_run_id,
            status=last_run.status,
            started_at=last_run.started_at,
            completed_at=last_run.completed_at,
            stocks_analyzed=last_run.stocks_analyzed,
            candidates_screened=last_run.candidates_screened,
            trades_approved=last_run.trades_approved,
            trades_executed=last_run.trades_executed,
            errors=last_run.errors,
        )

    return PipelineStatusResponse(
        status=getattr(app_state, "pipeline_status", None),
        last_run=last_run_info,
    )
