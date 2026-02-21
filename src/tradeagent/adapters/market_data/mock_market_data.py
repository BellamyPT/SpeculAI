"""Mock market data adapter — serves pre-loaded historical data for backtesting."""

from __future__ import annotations

from datetime import date

from tradeagent.adapters.base import (
    FundamentalSnapshot,
    MarketDataAdapter,
    PriceBar,
    ValidationResult,
)


class MockMarketDataAdapter(MarketDataAdapter):
    """Market data adapter that serves pre-loaded price/fundamental data.

    Critical for backtesting: ``fetch_prices()`` filters by date range
    to prevent lookahead bias.
    """

    def __init__(self) -> None:
        self._prices: dict[str, list[PriceBar]] = {}  # ticker -> sorted bars
        self._fundamentals: dict[str, FundamentalSnapshot] = {}

    def load_prices(self, data: dict[str, list[PriceBar]]) -> None:
        """Load price data. Bars should be sorted by date ascending."""
        self._prices = data

    def load_fundamentals(self, data: dict[str, FundamentalSnapshot]) -> None:
        """Load fundamental snapshot data."""
        self._fundamentals = data

    async def fetch_prices(
        self,
        tickers: list[str],
        start: date,
        end: date,
        *,
        batch_size: int = 100,
    ) -> dict[str, ValidationResult]:
        """Return pre-loaded prices filtered to [start, end] — no lookahead."""
        results: dict[str, ValidationResult] = {}
        for ticker in tickers:
            bars = self._prices.get(ticker, [])
            filtered = [b for b in bars if start <= b.date <= end]
            results[ticker] = ValidationResult(
                ticker=ticker,
                valid_bars=filtered,
            )
        return results

    async def fetch_fundamentals(
        self,
        tickers: list[str],
    ) -> dict[str, FundamentalSnapshot]:
        """Return pre-loaded fundamentals for requested tickers."""
        return {t: self._fundamentals[t] for t in tickers if t in self._fundamentals}
