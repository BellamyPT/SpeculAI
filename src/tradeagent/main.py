from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tradeagent.config import Settings
from tradeagent.core.exceptions import TradeAgentError
from tradeagent.core.logging import get_logger, setup_logging
from tradeagent.database import get_async_engine
from tradeagent.api.routes.decisions import router as decisions_router
from tradeagent.api.routes.health import router as health_router
from tradeagent.api.routes.pipeline import router as pipeline_router
from tradeagent.api.routes.portfolio import router as portfolio_router
from tradeagent.api.routes.trades import router as trades_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown."""
    settings = Settings.from_yaml()
    setup_logging(settings.log_level)

    engine = get_async_engine(settings)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    app.state.session_factory = session_factory
    app.state.engine = engine
    app.state.settings = settings

    # Pipeline state
    app.state.pipeline_status = None
    app.state.last_pipeline_run = None

    # Adapters
    from tradeagent.adapters.market_data.yfinance_adapter import YFinanceAdapter
    from tradeagent.adapters.llm.claude_cli import ClaudeCLIAdapter
    from tradeagent.adapters.news.perplexity_adapter import PerplexityNewsAdapter
    from tradeagent.services.pipeline import PipelineService
    from tradeagent.scheduler import PipelineScheduler

    market_data_adapter = YFinanceAdapter()
    llm_adapter = ClaudeCLIAdapter(
        cli_path=settings.claude_cli_path,
        timeout_seconds=settings.claude_cli_timeout,
        max_retries=settings.pipeline.max_llm_retries,
        system_prompt_path=settings.llm.system_prompt_path,
    )
    news_adapter = PerplexityNewsAdapter(
        api_key=settings.perplexity_api_key,
        model=settings.perplexity_model,
    )

    # Broker (optional)
    broker_adapter = None
    if settings.t212_api_key:
        from tradeagent.adapters.broker.trading212 import Trading212Adapter

        broker_adapter = Trading212Adapter(
            api_key=settings.t212_api_key,
            base_url=settings.t212_base_url,
        )

    app.state.broker_adapter = broker_adapter

    pipeline_service = PipelineService(
        session_factory=session_factory,
        settings=settings,
        market_data_adapter=market_data_adapter,
        llm_adapter=llm_adapter,
        news_adapter=news_adapter,
        broker_adapter=broker_adapter,
    )
    app.state.pipeline_service = pipeline_service

    # Scheduler
    scheduler = PipelineScheduler(
        pipeline_service,
        app.state,
        hour=settings.pipeline.schedule_hour,
        minute=settings.pipeline.schedule_minute,
    )
    scheduler.start()

    logger.info("application_started")
    yield

    scheduler.stop()

    # Cleanup adapters
    if hasattr(news_adapter, "close"):
        await news_adapter.close()
    if broker_adapter and hasattr(broker_adapter, "close"):
        await broker_adapter.close()

    await engine.dispose()
    logger.info("application_stopped")


def _build_error_response(
    code: str, message: str, details: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="SpeculAI", version="0.1.0", lifespan=lifespan)

    # CORS
    origins = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    settings = Settings.from_yaml()
    if settings.frontend_url not in origins:
        origins.append(settings.frontend_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {"field": ".".join(str(loc) for loc in e["loc"]), "issue": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=400,
            content=_build_error_response("VALIDATION_ERROR", "Invalid request", details),
        )

    @app.exception_handler(TradeAgentError)
    async def tradeagent_exception_handler(
        request: Request, exc: TradeAgentError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=_build_error_response(
                type(exc).__name__.upper(),
                str(exc),
            ),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_build_error_response(
                "INTERNAL_ERROR", "An unexpected error occurred"
            ),
        )

    # Routes
    app.include_router(health_router, prefix="/api")
    app.include_router(portfolio_router, prefix="/api")
    app.include_router(trades_router, prefix="/api")
    app.include_router(decisions_router, prefix="/api")
    app.include_router(pipeline_router, prefix="/api")

    return app


app = create_app()
