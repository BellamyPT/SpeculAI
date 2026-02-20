"""Tests for the ScreeningService."""

from __future__ import annotations

import pytest

from tradeagent.config import ScreeningConfig
from tradeagent.services.screening import CandidateScore, ScreeningService


@pytest.fixture
def config() -> ScreeningConfig:
    return ScreeningConfig()


@pytest.fixture
def service(config: ScreeningConfig) -> ScreeningService:
    return ScreeningService(config)


def _make_stock(
    stock_id: int = 1,
    ticker: str = "AAPL",
    sector: str = "Technology",
    rsi: float | None = 45.0,
    macd_direction: str = "bullish",
    macd_histogram: float = 0.5,
    pband: float = 0.3,
    sma_cross_bullish: bool | None = True,
    latest_volume: int = 5_000_000,
    volume_sma: float = 3_000_000,
    pe_ratio: float | None = 20.0,
    market_cap: float | None = 1_000_000_000,
) -> dict:
    return {
        "stock_id": stock_id,
        "ticker": ticker,
        "sector": sector,
        "indicators": {
            "rsi": rsi,
            "macd": {
                "histogram": macd_histogram,
                "direction": macd_direction,
            } if macd_direction else None,
            "bollinger": {"pband": pband} if pband is not None else None,
            "sma_cross_bullish": sma_cross_bullish,
            "latest_volume": latest_volume,
            "volume_sma": volume_sma,
        },
        "fundamentals": {
            "pe_ratio": pe_ratio,
            "market_cap": market_cap,
        },
    }


class TestScoringIndividual:
    def test_score_rsi_oversold(self, service):
        """Oversold RSI (30) should score high."""
        score = service._score_rsi({"rsi": 30.0})
        assert score == pytest.approx(1.0)

    def test_score_rsi_overbought(self, service):
        """Overbought RSI (70) should score 0."""
        score = service._score_rsi({"rsi": 70.0})
        assert score == pytest.approx(0.0)

    def test_score_rsi_midrange(self, service):
        """RSI 50 → (70-50)/40 = 0.5."""
        score = service._score_rsi({"rsi": 50.0})
        assert score == pytest.approx(0.5)

    def test_score_rsi_none(self, service):
        score = service._score_rsi({"rsi": None})
        assert score == 0.0

    def test_score_macd_bullish(self, service):
        score = service._score_macd(
            {"macd": {"histogram": 0.5, "direction": "bullish"}}
        )
        assert score == 1.0

    def test_score_macd_bearish(self, service):
        score = service._score_macd(
            {"macd": {"histogram": -0.5, "direction": "bearish"}}
        )
        assert score == 0.0

    def test_score_macd_neutral(self, service):
        score = service._score_macd(
            {"macd": {"histogram": 0.1, "direction": "neutral"}}
        )
        assert score == 0.5

    def test_score_macd_none(self, service):
        score = service._score_macd({"macd": None})
        assert score == 0.0

    def test_score_bollinger_near_lower(self, service):
        """pband = 0 → score = 1.0."""
        score = service._score_bollinger({"bollinger": {"pband": 0.0}})
        assert score == 1.0

    def test_score_bollinger_near_upper(self, service):
        """pband = 1.0 → score = 0.0."""
        score = service._score_bollinger({"bollinger": {"pband": 1.0}})
        assert score == 0.0

    def test_score_sma_cross_bullish(self, service):
        score = service._score_sma_cross({"sma_cross_bullish": True})
        assert score == 1.0

    def test_score_sma_cross_bearish(self, service):
        score = service._score_sma_cross({"sma_cross_bullish": False})
        assert score == 0.0

    def test_score_sma_cross_none(self, service):
        score = service._score_sma_cross({"sma_cross_bullish": None})
        assert score == 0.5

    def test_score_volume_above_threshold(self, service):
        score = service._score_volume_anomaly(
            {"latest_volume": 6_000_000, "volume_sma": 3_000_000}
        )
        # ratio = 6M / (3M * 1.5) = 1.333
        assert score > 0

    def test_score_volume_below_threshold(self, service):
        score = service._score_volume_anomaly(
            {"latest_volume": 1_000_000, "volume_sma": 3_000_000}
        )
        assert score == 0.0

    def test_score_pe_low(self, service):
        """PE = 15 → (25-15)/10 = 1.0."""
        score = service._score_pe_undervaluation({"pe_ratio": 15.0})
        assert score == pytest.approx(1.0)

    def test_score_pe_high(self, service):
        """PE = 35 → (25-35)/10 = -1.0 → clamped to 0."""
        score = service._score_pe_undervaluation({"pe_ratio": 35.0})
        assert score == 0.0

    def test_score_pe_none(self, service):
        score = service._score_pe_undervaluation({"pe_ratio": None})
        assert score == 0.0


class TestWeightedScore:
    def test_all_ones(self, service):
        components = {
            "rsi": 1.0,
            "macd": 1.0,
            "bollinger": 1.0,
            "sma_cross": 1.0,
            "volume_anomaly": 1.0,
            "pe_undervaluation": 1.0,
        }
        total = service._compute_weighted_score(components)
        assert total == pytest.approx(1.0)

    def test_all_zeros(self, service):
        components = {
            "rsi": 0.0,
            "macd": 0.0,
            "bollinger": 0.0,
            "sma_cross": 0.0,
            "volume_anomaly": 0.0,
            "pe_undervaluation": 0.0,
        }
        total = service._compute_weighted_score(components)
        assert total == pytest.approx(0.0)


class TestScoreAndRank:
    def test_sorts_by_score(self, service):
        stocks = [
            _make_stock(stock_id=1, ticker="LOW", rsi=60.0, pe_ratio=30.0),
            _make_stock(stock_id=2, ticker="HIGH", rsi=30.0, pe_ratio=15.0),
        ]
        result = service.score_and_rank(stocks, set())
        assert result[0].ticker == "HIGH"
        assert result[1].ticker == "LOW"
        assert result[0].total_score >= result[1].total_score

    def test_portfolio_always_included(self, service):
        """Stocks in portfolio bypass market cap filter."""
        stock = _make_stock(stock_id=1, ticker="SMALL", market_cap=100)
        result = service.score_and_rank([stock], {1})
        assert len(result) == 1
        assert result[0].in_portfolio is True

    def test_market_cap_filter(self, service):
        """Stocks below min_market_cap are excluded unless in portfolio."""
        stock = _make_stock(stock_id=1, ticker="TINY", market_cap=100)
        result = service.score_and_rank([stock], set())
        assert len(result) == 0

    def test_max_candidates_cap(self):
        config = ScreeningConfig(max_candidates=2)
        service = ScreeningService(config)
        stocks = [
            _make_stock(stock_id=i, ticker=f"S{i}")
            for i in range(5)
        ]
        result = service.score_and_rank(stocks, set())
        assert len(result) == 2

    def test_none_market_cap_included(self, service):
        """Stocks with no market cap data are included (not filtered)."""
        stock = _make_stock(stock_id=1, ticker="UNK", market_cap=None)
        result = service.score_and_rank([stock], set())
        assert len(result) == 1
