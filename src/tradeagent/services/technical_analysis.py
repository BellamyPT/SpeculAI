"""Technical analysis engine — computes indicators from price data."""

from __future__ import annotations

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD, SMAIndicator
from ta.volatility import BollingerBands

from tradeagent.adapters.base import PriceBar
from tradeagent.config import TechnicalAnalysisConfig
from tradeagent.core.logging import get_logger

log = get_logger(__name__)


class TechnicalAnalysisService:
    """Compute RSI, MACD, Bollinger Bands, SMA, EMA, and volume SMA."""

    def __init__(self, config: TechnicalAnalysisConfig) -> None:
        self._cfg = config

    # ── Public API ───────────────────────────────────────────────────

    def compute_indicators(self, df: pd.DataFrame) -> dict[str, object]:
        """Compute all indicators on a DataFrame with OHLCV columns.

        Returns a structured dict. Individual indicator failures yield
        ``None`` for that key but do not affect other indicators.
        """
        if df.empty or "close" not in df.columns:
            return self._empty_result(df)

        close = df["close"].astype(float)
        volume = df["volume"].astype(float) if "volume" in df.columns else None
        data_points = len(df)

        result: dict[str, object] = {
            "latest_close": float(close.iloc[-1]),
            "latest_volume": int(df["volume"].iloc[-1]) if volume is not None else 0,
            "data_points": data_points,
        }

        result["rsi"] = self._compute_rsi(close, data_points)
        result["macd"] = self._compute_macd(close, data_points)
        result["bollinger"] = self._compute_bollinger(close, data_points)
        result["sma_short"] = self._compute_sma(close, self._cfg.sma_short, data_points)
        result["sma_long"] = self._compute_sma(close, self._cfg.sma_long, data_points)
        result["ema_short"] = self._compute_ema(close, self._cfg.ema_short, data_points)
        result["ema_long"] = self._compute_ema(close, self._cfg.ema_long, data_points)
        result["volume_sma"] = self._compute_volume_sma(volume, data_points)

        # Derived signals
        sma_s = result["sma_short"]
        sma_l = result["sma_long"]
        result["sma_cross_bullish"] = (
            sma_s > sma_l if sma_s is not None and sma_l is not None else None
        )

        return result

    @staticmethod
    def prices_to_dataframe(prices: list[PriceBar]) -> pd.DataFrame:
        """Convert a list of ``PriceBar`` DTOs to a pandas DataFrame."""
        if not prices:
            return pd.DataFrame()
        rows = [
            {
                "date": p.date,
                "open": float(p.open),
                "high": float(p.high),
                "low": float(p.low),
                "close": float(p.close),
                "adj_close": float(p.adj_close),
                "volume": p.volume,
            }
            for p in prices
        ]
        df = pd.DataFrame(rows)
        df.sort_values("date", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    # ── Private indicator methods ────────────────────────────────────

    def _compute_rsi(self, close: pd.Series, data_points: int) -> float | None:
        if data_points < self._cfg.rsi_period + 1:
            return None
        try:
            rsi = RSIIndicator(close=close, window=self._cfg.rsi_period)
            val = rsi.rsi().iloc[-1]
            return None if pd.isna(val) else round(float(val), 2)
        except Exception:
            log.warning("rsi_computation_failed", exc_info=True)
            return None

    def _compute_macd(self, close: pd.Series, data_points: int) -> dict[str, object] | None:
        if data_points < self._cfg.macd_slow + self._cfg.macd_signal:
            return None
        try:
            macd = MACD(
                close=close,
                window_slow=self._cfg.macd_slow,
                window_fast=self._cfg.macd_fast,
                window_sign=self._cfg.macd_signal,
            )
            macd_line = macd.macd().iloc[-1]
            signal_line = macd.macd_signal().iloc[-1]
            histogram = macd.macd_diff().iloc[-1]

            if any(pd.isna(v) for v in (macd_line, signal_line, histogram)):
                return None

            if histogram > 0 and macd_line > signal_line:
                direction = "bullish"
            elif histogram < 0 and macd_line < signal_line:
                direction = "bearish"
            else:
                direction = "neutral"

            return {
                "macd_line": round(float(macd_line), 4),
                "signal_line": round(float(signal_line), 4),
                "histogram": round(float(histogram), 4),
                "direction": direction,
            }
        except Exception:
            log.warning("macd_computation_failed", exc_info=True)
            return None

    def _compute_bollinger(self, close: pd.Series, data_points: int) -> dict[str, object] | None:
        if data_points < self._cfg.bollinger_period:
            return None
        try:
            bb = BollingerBands(
                close=close,
                window=self._cfg.bollinger_period,
                window_dev=self._cfg.bollinger_std,
            )
            upper = bb.bollinger_hband().iloc[-1]
            middle = bb.bollinger_mavg().iloc[-1]
            lower = bb.bollinger_lband().iloc[-1]
            pband = bb.bollinger_pband().iloc[-1]

            if any(pd.isna(v) for v in (upper, middle, lower, pband)):
                return None

            return {
                "upper": round(float(upper), 4),
                "middle": round(float(middle), 4),
                "lower": round(float(lower), 4),
                "pband": round(float(pband), 4),
            }
        except Exception:
            log.warning("bollinger_computation_failed", exc_info=True)
            return None

    def _compute_sma(self, close: pd.Series, window: int, data_points: int) -> float | None:
        if data_points < window:
            return None
        try:
            sma = SMAIndicator(close=close, window=window)
            val = sma.sma_indicator().iloc[-1]
            return None if pd.isna(val) else round(float(val), 4)
        except Exception:
            log.warning("sma_computation_failed", window=window, exc_info=True)
            return None

    def _compute_ema(self, close: pd.Series, window: int, data_points: int) -> float | None:
        if data_points < window:
            return None
        try:
            ema = EMAIndicator(close=close, window=window)
            val = ema.ema_indicator().iloc[-1]
            return None if pd.isna(val) else round(float(val), 4)
        except Exception:
            log.warning("ema_computation_failed", window=window, exc_info=True)
            return None

    def _compute_volume_sma(self, volume: pd.Series | None, data_points: int) -> float | None:
        if volume is None or data_points < self._cfg.volume_sma_period:
            return None
        try:
            sma = SMAIndicator(close=volume, window=self._cfg.volume_sma_period)
            val = sma.sma_indicator().iloc[-1]
            return None if pd.isna(val) else round(float(val), 2)
        except Exception:
            log.warning("volume_sma_computation_failed", exc_info=True)
            return None

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _empty_result(df: pd.DataFrame) -> dict[str, object]:
        return {
            "rsi": None,
            "macd": None,
            "bollinger": None,
            "sma_short": None,
            "sma_long": None,
            "ema_short": None,
            "ema_long": None,
            "volume_sma": None,
            "latest_close": 0.0,
            "latest_volume": 0,
            "sma_cross_bullish": None,
            "data_points": len(df),
        }
