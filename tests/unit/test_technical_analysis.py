"""Tests for the TechnicalAnalysisService."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from tradeagent.adapters.base import PriceBar
from tradeagent.config import TechnicalAnalysisConfig
from tradeagent.services.technical_analysis import TechnicalAnalysisService


@pytest.fixture
def config() -> TechnicalAnalysisConfig:
    return TechnicalAnalysisConfig()


@pytest.fixture
def service(config: TechnicalAnalysisConfig) -> TechnicalAnalysisService:
    return TechnicalAnalysisService(config)


def _make_df(n: int, base_close: float = 100.0) -> pd.DataFrame:
    """Create a DataFrame with *n* rows of synthetic OHLCV data."""
    import numpy as np

    rng = np.random.default_rng(42)
    closes = base_close + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=n, freq="B"),
            "open": closes - 0.5,
            "high": closes + 1.0,
            "low": closes - 1.0,
            "close": closes,
            "adj_close": closes,
            "volume": rng.integers(1_000_000, 10_000_000, size=n),
        }
    )


class TestComputeIndicators:
    def test_sufficient_data_returns_all_indicators(self, service):
        df = _make_df(250)
        result = service.compute_indicators(df)

        assert result["rsi"] is not None
        assert isinstance(result["rsi"], float)
        assert 0 <= result["rsi"] <= 100

        assert result["macd"] is not None
        assert "macd_line" in result["macd"]
        assert "signal_line" in result["macd"]
        assert "histogram" in result["macd"]
        assert result["macd"]["direction"] in ("bullish", "bearish", "neutral")

        assert result["bollinger"] is not None
        assert "upper" in result["bollinger"]
        assert "middle" in result["bollinger"]
        assert "lower" in result["bollinger"]
        assert "pband" in result["bollinger"]

        assert result["sma_short"] is not None
        assert result["sma_long"] is not None
        assert result["ema_short"] is not None
        assert result["ema_long"] is not None
        assert result["volume_sma"] is not None

        assert isinstance(result["sma_cross_bullish"], bool)
        assert result["data_points"] == 250
        assert result["latest_close"] != 0

    def test_insufficient_data_returns_none(self, service):
        df = _make_df(5)
        result = service.compute_indicators(df)

        assert result["rsi"] is None
        assert result["macd"] is None
        assert result["bollinger"] is None
        assert result["sma_short"] is None
        assert result["sma_long"] is None
        assert result["volume_sma"] is None
        assert result["sma_cross_bullish"] is None
        assert result["data_points"] == 5

    def test_empty_dataframe(self, service):
        df = pd.DataFrame()
        result = service.compute_indicators(df)

        assert result["rsi"] is None
        assert result["latest_close"] == 0.0
        assert result["data_points"] == 0

    def test_partial_indicators(self, service):
        """With enough data for RSI/EMA but not SMA(200)."""
        df = _make_df(60)
        result = service.compute_indicators(df)

        assert result["rsi"] is not None
        assert result["ema_short"] is not None
        assert result["ema_long"] is not None
        assert result["sma_short"] is not None
        # Not enough for SMA(200)
        assert result["sma_long"] is None
        assert result["sma_cross_bullish"] is None

    def test_volume_sma_computed(self, service):
        df = _make_df(30)
        result = service.compute_indicators(df)
        assert result["volume_sma"] is not None
        assert result["volume_sma"] > 0

    def test_latest_close_and_volume(self, service):
        df = _make_df(50)
        result = service.compute_indicators(df)
        assert result["latest_close"] == float(df["close"].iloc[-1])
        assert result["latest_volume"] == int(df["volume"].iloc[-1])


class TestPricesToDataframe:
    def test_converts_price_bars(self):
        bars = [
            PriceBar(
                ticker="AAPL",
                date=date(2024, 1, i + 1),
                open=Decimal("150"),
                high=Decimal("155"),
                low=Decimal("149"),
                close=Decimal(str(150 + i)),
                adj_close=Decimal(str(150 + i)),
                volume=1_000_000,
            )
            for i in range(5)
        ]
        df = TechnicalAnalysisService.prices_to_dataframe(bars)
        assert len(df) == 5
        assert list(df.columns) == [
            "date", "open", "high", "low", "close", "adj_close", "volume"
        ]
        # Sorted by date
        assert df["date"].iloc[0] == date(2024, 1, 1)
        assert df["date"].iloc[-1] == date(2024, 1, 5)

    def test_empty_list_returns_empty_df(self):
        df = TechnicalAnalysisService.prices_to_dataframe([])
        assert df.empty
