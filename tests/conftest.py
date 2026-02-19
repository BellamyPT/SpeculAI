import pytest

from tradeagent.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Provide default Settings instance for tests."""
    return Settings()


@pytest.fixture
def async_engine(settings):
    """Create an async SQLAlchemy engine. Skip if PostgreSQL is unavailable."""
    pytest.importorskip("asyncpg")

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.database_url_async, echo=False)

    yield engine

    # Cleanup handled by caller or test


@pytest.fixture
async def async_session(async_engine):
    """Create an async session for DB tests. Skip if PostgreSQL is unavailable."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    # Verify connection works; skip if not
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("PostgreSQL not available")

    session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()
