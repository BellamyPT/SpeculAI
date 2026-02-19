"""Concrete MarketDataAdapter backed by the yfinance library."""

from __future__ import annotations

import asyncio
import math
from datetime import date
from decimal import Decimal, InvalidOperation

import yfinance as yf

from tradeagent.adapters.base import (
    FundamentalSnapshot,
    MarketDataAdapter,
    PriceBar,
    ValidationResult,
)
from tradeagent.core.exceptions import DataIngestionError
from tradeagent.core.logging import get_logger

log = get_logger(__name__)

# Mapping from yfinance .info keys → FundamentalSnapshot field names.
_FUNDAMENTAL_FIELD_MAP: dict[str, str] = {
    "shortName": "name",
    "exchange": "exchange",
    "currency": "currency",
    "sector": "sector",
    "industry": "industry",
    "country": "country",
    "marketCap": "market_cap",
    "trailingPE": "pe_ratio",
    "forwardPE": "forward_pe",
    "pegRatio": "peg_ratio",
    "priceToBook": "price_to_book",
    "priceToSalesTrailing12Months": "price_to_sales",
    "dividendYield": "dividend_yield",
    "trailingEps": "eps",
    "revenueGrowth": "revenue_growth",
    "earningsGrowth": "earnings_growth",
    "profitMargins": "profit_margin",
    "debtToEquity": "debt_to_equity",
    "currentRatio": "current_ratio",
    "beta": "beta",
}

# Fields that should be converted to Decimal (numeric fundamentals).
_DECIMAL_FIELDS: set[str] = {
    "market_cap",
    "pe_ratio",
    "forward_pe",
    "peg_ratio",
    "price_to_book",
    "price_to_sales",
    "dividend_yield",
    "eps",
    "revenue_growth",
    "earnings_growth",
    "profit_margin",
    "debt_to_equity",
    "current_ratio",
    "beta",
}


def _safe_decimal(value: object) -> Decimal | None:
    """Convert a numeric value to Decimal, returning None for missing/invalid."""
    if value is None:
        return None
    try:
        d = Decimal(str(value))
        if d.is_nan() or d.is_infinite():
            return None
        return d
    except (InvalidOperation, ValueError, TypeError):
        return None


def _is_valid_price(value: object) -> bool:
    """Return True if *value* is a finite number > 0."""
    if value is None:
        return False
    try:
        f = float(value)
        return math.isfinite(f) and f > 0
    except (ValueError, TypeError):
        return False


class YFinanceAdapter(MarketDataAdapter):
    """Market data adapter using the yfinance library.

    yfinance is synchronous; all blocking calls are wrapped via
    ``asyncio.to_thread`` so they don't block the event loop.
    """

    # ── Public interface ─────────────────────────────────────────────

    async def fetch_prices(
        self,
        tickers: list[str],
        start: date,
        end: date,
        *,
        batch_size: int = 100,
    ) -> dict[str, ValidationResult]:
        """Download OHLCV data in batches and validate each row."""
        if not tickers:
            return {}

        results: dict[str, ValidationResult] = {}
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            batch_results = await asyncio.to_thread(
                self._fetch_price_batch, batch, start, end
            )
            results.update(batch_results)

        return results

    async def fetch_fundamentals(
        self,
        tickers: list[str],
    ) -> dict[str, FundamentalSnapshot]:
        """Fetch fundamental snapshots one ticker at a time."""
        if not tickers:
            return {}

        return await asyncio.to_thread(self._fetch_fundamentals_sync, tickers)

    # ── Private synchronous helpers ──────────────────────────────────

    def _fetch_price_batch(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> dict[str, ValidationResult]:
        """Download a batch of tickers via yf.download and validate."""
        results: dict[str, ValidationResult] = {
            t: ValidationResult(ticker=t) for t in tickers
        }

        try:
            df = yf.download(
                tickers=tickers,
                start=start.isoformat(),
                end=end.isoformat(),
                auto_adjust=True,
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception as exc:
            log.error(
                "yfinance download failed",
                tickers=tickers,
                error=str(exc),
            )
            raise DataIngestionError(
                f"yfinance download failed for batch: {exc}"
            ) from exc

        if df is None or df.empty:
            log.warning("yfinance returned empty DataFrame", tickers=tickers)
            return results

        # yf.download returns different structures for single vs multi-ticker.
        if len(tickers) == 1:
            self._parse_single_ticker_df(tickers[0], df, results)
        else:
            self._parse_multi_ticker_df(tickers, df, results)

        return results

    def _parse_single_ticker_df(
        self,
        ticker: str,
        df: object,
        results: dict[str, ValidationResult],
    ) -> None:
        """Parse a DataFrame returned by yf.download for a single ticker."""
        import pandas as pd

        if not isinstance(df, pd.DataFrame) or df.empty:
            return

        vr = results[ticker]
        for row_date, row in df.iterrows():
            ts = pd.Timestamp(row_date)
            bar_date = ts.date()
            bar_or_reason = self._validate_price_row(ticker, bar_date, row)
            if isinstance(bar_or_reason, PriceBar):
                vr.valid_bars.append(bar_or_reason)
            else:
                vr.rejected_count += 1
                vr.rejection_reasons.append(bar_or_reason)

    def _parse_multi_ticker_df(
        self,
        tickers: list[str],
        df: object,
        results: dict[str, ValidationResult],
    ) -> None:
        """Parse a DataFrame returned by yf.download for multiple tickers."""
        import pandas as pd

        if not isinstance(df, pd.DataFrame) or df.empty:
            return

        for ticker in tickers:
            vr = results[ticker]
            try:
                ticker_df = df[ticker]
            except KeyError:
                log.warning("ticker_not_in_download", ticker=ticker)
                continue

            if isinstance(ticker_df, pd.DataFrame) and not ticker_df.empty:
                for row_date, row in ticker_df.iterrows():
                    ts = pd.Timestamp(row_date)
                    bar_date = ts.date()
                    bar_or_reason = self._validate_price_row(
                        ticker, bar_date, row
                    )
                    if isinstance(bar_or_reason, PriceBar):
                        vr.valid_bars.append(bar_or_reason)
                    else:
                        vr.rejected_count += 1
                        vr.rejection_reasons.append(bar_or_reason)

    @staticmethod
    def _validate_price_row(
        ticker: str,
        bar_date: date,
        row: object,
    ) -> PriceBar | str:
        """Validate a single OHLCV row. Returns PriceBar or rejection reason."""
        try:
            o = row.get("Open") if hasattr(row, "get") else getattr(row, "Open", None)
            h = row.get("High") if hasattr(row, "get") else getattr(row, "High", None)
            lo = row.get("Low") if hasattr(row, "get") else getattr(row, "Low", None)
            c = row.get("Close") if hasattr(row, "get") else getattr(row, "Close", None)
            v = row.get("Volume") if hasattr(row, "get") else getattr(row, "Volume", None)
        except Exception:
            return f"{ticker} {bar_date}: failed to extract fields"

        # Prices must be positive and finite; volume may be zero.
        for label, val in [("Open", o), ("High", h), ("Low", lo), ("Close", c)]:
            if not _is_valid_price(val):
                return f"{ticker} {bar_date}: invalid {label}={val}"

        vol = int(v) if v is not None and math.isfinite(float(v)) else 0

        return PriceBar(
            ticker=ticker,
            date=bar_date,
            open=Decimal(str(float(o))),
            high=Decimal(str(float(h))),
            low=Decimal(str(float(lo))),
            close=Decimal(str(float(c))),
            adj_close=Decimal(str(float(c))),  # auto_adjust=True → Close is adjusted
            volume=vol,
        )

    def _fetch_fundamentals_sync(
        self,
        tickers: list[str],
    ) -> dict[str, FundamentalSnapshot]:
        """Fetch fundamental info for each ticker sequentially."""
        snapshots: dict[str, FundamentalSnapshot] = {}
        today = date.today()

        for ticker in tickers:
            try:
                info = yf.Ticker(ticker).info or {}
            except Exception as exc:
                log.warning(
                    "yfinance_fundamental_failed",
                    ticker=ticker,
                    error=str(exc),
                )
                continue

            if not info or info.get("regularMarketPrice") is None:
                log.debug("no_fundamental_data", ticker=ticker)
                continue

            kwargs: dict[str, object] = {
                "ticker": ticker,
                "snapshot_date": today,
            }

            for yf_key, field_name in _FUNDAMENTAL_FIELD_MAP.items():
                raw = info.get(yf_key)
                if raw is None:
                    continue
                if field_name in _DECIMAL_FIELDS:
                    kwargs[field_name] = _safe_decimal(raw)
                else:
                    kwargs[field_name] = str(raw) if raw else None

            snapshots[ticker] = FundamentalSnapshot(**kwargs)  # type: ignore[arg-type]

        return snapshots
