"""Pipeline scheduler — runs the daily pipeline on a cron schedule."""

from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from tradeagent.core.logging import get_logger
from tradeagent.core.types import PipelineStatus

log = get_logger(__name__)


class PipelineScheduler:
    """Wraps APScheduler to trigger the daily pipeline."""

    def __init__(
        self,
        pipeline_service,
        app_state,
        *,
        hour: int = 7,
        minute: int = 0,
    ) -> None:
        self._pipeline = pipeline_service
        self._app_state = app_state
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._trigger_pipeline,
            trigger=CronTrigger(hour=hour, minute=minute),
            id="daily_pipeline",
            replace_existing=True,
        )

    def start(self) -> None:
        self._scheduler.start()
        log.info("scheduler_started")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")

    async def _trigger_pipeline(self) -> None:
        """Check if pipeline is already running, then trigger."""
        if self._app_state.pipeline_status == PipelineStatus.RUNNING:
            log.warning("pipeline_already_running_skipping_schedule")
            return

        self._app_state.pipeline_status = PipelineStatus.RUNNING
        try:
            result = await self._pipeline.run()
            self._app_state.pipeline_status = result.status
            self._app_state.last_pipeline_run = result
        except Exception:
            self._app_state.pipeline_status = PipelineStatus.FAILED
            log.error("scheduled_pipeline_failed", exc_info=True)
