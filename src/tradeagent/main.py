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
from tradeagent.api.routes.health import router as health_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown."""
    settings = Settings.from_yaml()
    setup_logging(settings.log_level)

    engine = get_async_engine(settings)
    app.state.session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    app.state.engine = engine
    app.state.settings = settings

    logger.info("application_started")
    yield

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

    return app


app = create_app()
