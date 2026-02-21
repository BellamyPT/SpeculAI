import pytest

from tradeagent.config import Settings

# Re-export factories for easy access in all tests
from tests.factories import (  # noqa: F401
    BenchmarkFactory,
    BenchmarkPriceFactory,
    DecisionContextItemFactory,
    DecisionReportFactory,
    PortfolioSnapshotFactory,
    PositionFactory,
    PositionSnapshotFactory,
    StockFactory,
    StockFundamentalFactory,
    StockPriceFactory,
    TradeFactory,
)


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
async def db_tables(async_engine):
    """Create all tables before tests, drop them after.

    Uses Base.metadata directly — no Alembic needed in tests.
    """
    from sqlalchemy import text
    from tradeagent.models import Base

    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("PostgreSQL not available")

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def async_session(async_engine, db_tables):
    """Create an async session for DB tests. Skip if PostgreSQL is unavailable."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def sample_stock(async_session):
    """Insert and return a sample Stock row for tests."""
    from tradeagent.models import Stock

    stock = Stock(
        ticker="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        sector="Technology",
        industry="Consumer Electronics",
        country="US",
        currency="USD",
        is_active=True,
    )
    async_session.add(stock)
    await async_session.flush()
    return stock


@pytest.fixture
async def sample_benchmark(async_session):
    """Insert and return a sample Benchmark row for tests."""
    from tradeagent.models import Benchmark

    benchmark = Benchmark(symbol="^GSPC", name="S&P 500")
    async_session.add(benchmark)
    await async_session.flush()
    return benchmark
