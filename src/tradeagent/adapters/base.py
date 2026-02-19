"""Abstract base classes and DTOs for all external service adapters.

Services import ABCs and DTOs from this module.
Concrete adapters also import from here to implement the interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any


# ── DTOs ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PriceBar:
    """Single OHLCV bar for a ticker on a date."""

    ticker: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adj_close: Decimal
    volume: int


@dataclass(frozen=True, slots=True)
class FundamentalSnapshot:
    """Point-in-time fundamental data for a ticker."""

    ticker: str
    snapshot_date: date
    # Identification
    name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    # Valuation
    market_cap: Decimal | None = None
    pe_ratio: Decimal | None = None
    forward_pe: Decimal | None = None
    peg_ratio: Decimal | None = None
    price_to_book: Decimal | None = None
    price_to_sales: Decimal | None = None
    # Dividends & Earnings
    dividend_yield: Decimal | None = None
    eps: Decimal | None = None
    # Growth & Profitability
    revenue_growth: Decimal | None = None
    earnings_growth: Decimal | None = None
    profit_margin: Decimal | None = None
    # Risk
    debt_to_equity: Decimal | None = None
    current_ratio: Decimal | None = None
    beta: Decimal | None = None
    # Calendar
    next_earnings_date: date | None = None


@dataclass(slots=True)
class ValidationResult:
    """Result of validating fetched price data for a single ticker."""

    ticker: str
    valid_bars: list[PriceBar] = field(default_factory=list)
    rejected_count: int = 0
    rejection_reasons: list[str] = field(default_factory=list)
    missing_dates: list[date] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Response from the LLM adapter."""

    raw_text: str
    parsed: dict[str, Any]
    token_count: int
    response_time_seconds: float
    parse_success: bool


@dataclass(frozen=True, slots=True)
class NewsItem:
    """A single news article or summary."""

    source: str
    headline: str
    summary: str
    published_at: datetime | None
    url: str
    relevance_score: float | None = None


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """Request to place a trade via the broker adapter."""

    ticker: str
    side: str  # "BUY" or "SELL"
    quantity: Decimal
    order_type: str = "MARKET"  # "MARKET" or "LIMIT"
    limit_price: Decimal | None = None


@dataclass(frozen=True, slots=True)
class OrderStatus:
    """Status of a broker order."""

    broker_order_id: str
    ticker: str
    side: str
    status: str  # "PENDING", "FILLED", "FAILED", "CANCELLED"
    filled_quantity: Decimal | None = None
    filled_price: Decimal | None = None
    filled_at: datetime | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class BrokerPosition:
    """A position held at the broker."""

    ticker: str
    quantity: Decimal
    avg_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal


@dataclass(frozen=True, slots=True)
class BrokerInstrument:
    """An instrument available at the broker."""

    ticker: str
    name: str
    exchange: str
    currency: str
    isin: str | None = None
    min_quantity: Decimal | None = None


# ── Abstract Base Classes ────────────────────────────────────────────


class MarketDataAdapter(ABC):
    """Interface for fetching market prices and fundamental data."""

    @abstractmethod
    async def fetch_prices(
        self,
        tickers: list[str],
        start: date,
        end: date,
        *,
        batch_size: int = 100,
    ) -> dict[str, ValidationResult]:
        """Fetch OHLCV data for *tickers* between *start* and *end*.

        Returns a mapping of ticker -> ValidationResult containing valid
        PriceBars and any rejection/missing-date info.
        """

    @abstractmethod
    async def fetch_fundamentals(
        self,
        tickers: list[str],
    ) -> dict[str, FundamentalSnapshot]:
        """Fetch a point-in-time fundamental snapshot for each ticker."""


class LLMAdapter(ABC):
    """Interface for LLM-based analysis."""

    @abstractmethod
    async def analyze(
        self,
        analysis_package: dict[str, Any],
        *,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Send an analysis package to the LLM and return the parsed response."""


class NewsAdapter(ABC):
    """Interface for fetching financial news."""

    @abstractmethod
    async def query_news(
        self,
        topics: list[str],
        *,
        max_results_per_topic: int = 5,
    ) -> list[NewsItem]:
        """Query news articles for the given topics."""


class BrokerAdapter(ABC):
    """Interface for broker trade execution and portfolio queries."""

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderStatus:
        """Place a trade order via the broker."""

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        """Poll the status of a previously placed order."""

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Return all open positions at the broker."""

    @abstractmethod
    async def get_instruments(
        self,
        *,
        search: str | None = None,
    ) -> list[BrokerInstrument]:
        """List available instruments, optionally filtered by a search term."""
