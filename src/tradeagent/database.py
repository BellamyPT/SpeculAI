from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tradeagent.config import Settings


def get_async_engine(settings: Settings):
    """Create an async SQLAlchemy engine from settings."""
    return create_async_engine(
        settings.database_url_async,
        echo=False,
        pool_pre_ping=True,
    )


def get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory from settings."""
    engine = get_async_engine(settings)
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
