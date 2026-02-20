"""Stock screening service — score and rank candidates for the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from tradeagent.config import ScreeningConfig
from tradeagent.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class CandidateScore:
    """Scored stock candidate produced by the screening service."""

    stock_id: int
    ticker: str
    sector: str | None
    total_score: float
    component_scores: dict[str, float]
    indicators: dict[str, object]
    fundamentals: dict[str, object]
    in_portfolio: bool
    market_cap: float | None = None


class ScreeningService:
    """Score and rank stock candidates based on technical and fundamental signals."""

    def __init__(self, config: ScreeningConfig) -> None:
        self._cfg = config

    def score_and_rank(
        self,
        stocks_with_indicators: list[dict[str, object]],
        portfolio_stock_ids: set[int],
    ) -> list[CandidateScore]:
        """Score each stock, filter, sort by total_score descending, cap at max_candidates."""
        scored: list[CandidateScore] = []
        for item in stocks_with_indicators:
            try:
                candidate = self._score_single(item, portfolio_stock_ids)
                scored.append(candidate)
            except Exception:
                log.warning(
                    "scoring_failed",
                    ticker=item.get("ticker", "unknown"),
                    exc_info=True,
                )

        filtered = self._filter_candidates(scored, portfolio_stock_ids)
        filtered.sort(key=lambda c: c.total_score, reverse=True)
        return filtered[: self._cfg.max_candidates]

    # ── Scoring ──────────────────────────────────────────────────────

    def _score_single(
        self,
        item: dict[str, object],
        portfolio_stock_ids: set[int],
    ) -> CandidateScore:
        indicators = item.get("indicators", {}) or {}
        fundamentals = item.get("fundamentals", {}) or {}
        stock_id = int(item["stock_id"])

        components: dict[str, float] = {
            "rsi": self._score_rsi(indicators),
            "macd": self._score_macd(indicators),
            "bollinger": self._score_bollinger(indicators),
            "sma_cross": self._score_sma_cross(indicators),
            "volume_anomaly": self._score_volume_anomaly(indicators),
            "pe_undervaluation": self._score_pe_undervaluation(fundamentals),
        }
        total = self._compute_weighted_score(components)

        market_cap_raw = fundamentals.get("market_cap")
        market_cap = float(market_cap_raw) if market_cap_raw is not None else None

        return CandidateScore(
            stock_id=stock_id,
            ticker=str(item.get("ticker", "")),
            sector=str(item.get("sector", "")) if item.get("sector") else None,
            total_score=round(total, 4),
            component_scores=components,
            indicators=indicators,
            fundamentals=fundamentals,
            in_portfolio=stock_id in portfolio_stock_ids,
            market_cap=market_cap,
        )

    def _score_rsi(self, indicators: dict[str, object]) -> float:
        """RSI scoring: oversold scores high. ``max(0, min(1, (70 - rsi) / 40))``."""
        rsi = indicators.get("rsi")
        if rsi is None:
            return 0.0
        return max(0.0, min(1.0, (70.0 - float(rsi)) / 40.0))

    def _score_macd(self, indicators: dict[str, object]) -> float:
        """MACD scoring: bullish with positive histogram = 1.0."""
        macd = indicators.get("macd")
        if macd is None or not isinstance(macd, dict):
            return 0.0
        histogram = macd.get("histogram", 0)
        direction = macd.get("direction", "neutral")
        if histogram is not None and float(histogram) > 0 and direction == "bullish":
            return 1.0
        if direction == "bearish":
            return 0.0
        return 0.5

    def _score_bollinger(self, indicators: dict[str, object]) -> float:
        """Bollinger scoring: near lower band scores high. ``max(0, 1 - pband)``."""
        bb = indicators.get("bollinger")
        if bb is None or not isinstance(bb, dict):
            return 0.0
        pband = bb.get("pband")
        if pband is None:
            return 0.0
        return max(0.0, min(1.0, 1.0 - float(pband)))

    def _score_sma_cross(self, indicators: dict[str, object]) -> float:
        """SMA cross scoring: golden cross = 1.0, death cross = 0.0."""
        bullish = indicators.get("sma_cross_bullish")
        if bullish is None:
            return 0.5  # no signal → neutral
        return 1.0 if bullish else 0.0

    def _score_volume_anomaly(self, indicators: dict[str, object]) -> float:
        """Volume scoring: above-average volume relative to SMA."""
        latest_volume = indicators.get("latest_volume")
        volume_sma = indicators.get("volume_sma")
        if latest_volume is None or volume_sma is None or float(volume_sma) == 0:
            return 0.0
        multiplier = self._cfg.thresholds.volume_anomaly_multiplier
        ratio = float(latest_volume) / (float(volume_sma) * multiplier)
        if ratio < 1.0:
            return 0.0
        return min(1.0, ratio)

    def _score_pe_undervaluation(self, fundamentals: dict[str, object]) -> float:
        """P/E scoring: low P/E scores high. ``max(0, min(1, (25 - pe) / 10))``."""
        pe = fundamentals.get("pe_ratio")
        if pe is None:
            return 0.0
        return max(0.0, min(1.0, (25.0 - float(pe)) / 10.0))

    def _compute_weighted_score(self, component_scores: dict[str, float]) -> float:
        """Compute weighted sum from component scores and config weights."""
        w = self._cfg.weights
        return (
            component_scores.get("rsi", 0) * w.rsi
            + component_scores.get("macd", 0) * w.macd
            + component_scores.get("bollinger", 0) * w.bollinger
            + component_scores.get("sma_cross", 0) * w.sma_cross
            + component_scores.get("volume_anomaly", 0) * w.volume_anomaly
            + component_scores.get("pe_undervaluation", 0) * w.pe_undervaluation
        )

    def _filter_candidates(
        self,
        scored: list[CandidateScore],
        portfolio_stock_ids: set[int],
    ) -> list[CandidateScore]:
        """Filter out stocks below min market cap, but always keep portfolio holdings."""
        min_cap = self._cfg.min_market_cap
        return [
            c
            for c in scored
            if c.stock_id in portfolio_stock_ids
            or c.market_cap is None
            or c.market_cap >= min_cap
        ]
