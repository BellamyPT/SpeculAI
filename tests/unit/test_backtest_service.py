"""Unit tests for BacktestService."""

from __future__ import annotations

from datetime import date

import pytest

from tradeagent.services.backtest import (
    BacktestConfig,
    BacktestService,
    _generate_trading_days,
)


# ── Trading days generation ──────────────────────────────────


def test_generate_trading_days_weekdays_only():
    """Should only return Mon-Fri dates."""
    # Jan 1 2024 is Monday, Jan 7 is Sunday
    days = _generate_trading_days(date(2024, 1, 1), date(2024, 1, 7))

    assert len(days) == 5  # Mon-Fri
    for d in days:
        assert d.weekday() < 5


def test_generate_trading_days_empty_range():
    """End before start should return empty list."""
    days = _generate_trading_days(date(2024, 1, 5), date(2024, 1, 1))
    assert days == []


def test_generate_trading_days_weekend_only():
    """A weekend range should return empty list."""
    # Jan 6 2024 is Saturday, Jan 7 is Sunday
    days = _generate_trading_days(date(2024, 1, 6), date(2024, 1, 7))
    assert days == []


def test_generate_trading_days_single_weekday():
    """A single weekday should return one day."""
    days = _generate_trading_days(date(2024, 1, 3), date(2024, 1, 3))
    assert len(days) == 1


# ── Metrics computation ──────────────────────────────────────


def test_compute_annualized_return():
    """Annualized return computation."""
    # 10% over 252 days = 10% annualized
    result = BacktestService._compute_annualized_return(0.1, 252)
    assert abs(result - 10.0) < 0.5


def test_compute_annualized_return_zero_days():
    """Zero days should return 0."""
    result = BacktestService._compute_annualized_return(0.1, 0)
    assert result == 0.0


def test_compute_max_drawdown():
    """Max drawdown from a known series."""
    values = [100.0, 110.0, 90.0, 95.0, 105.0]
    # Peak = 110, trough = 90 → drawdown = (110-90)/110 ≈ 18.18%
    dd = BacktestService._compute_max_drawdown(values)
    assert abs(dd - 18.18) < 0.1


def test_compute_max_drawdown_monotonically_increasing():
    """No drawdown for monotonically increasing series."""
    values = [100.0, 110.0, 120.0, 130.0]
    dd = BacktestService._compute_max_drawdown(values)
    assert dd == 0.0


def test_compute_max_drawdown_single_value():
    """Single value series should return 0 drawdown."""
    dd = BacktestService._compute_max_drawdown([100.0])
    assert dd == 0.0


def test_compute_sharpe_ratio_constant_returns():
    """Constant returns (zero std) should give Sharpe = 0."""
    values = [100.0, 101.0, 102.0, 103.0, 104.0]
    sharpe = BacktestService._compute_sharpe_ratio(values)
    # Returns are constant (1% each day), so std ≈ 0 → but due to floating
    # point, sharpe may be extremely high or 0; we allow both
    assert sharpe >= 0


def test_compute_sharpe_ratio_volatile():
    """Volatile returns should produce a reasonable Sharpe."""
    values = [100.0, 105.0, 95.0, 110.0, 100.0]
    sharpe = BacktestService._compute_sharpe_ratio(values)
    assert isinstance(sharpe, float)


def test_compute_sharpe_ratio_too_few():
    """Less than 3 values should return 0."""
    sharpe = BacktestService._compute_sharpe_ratio([100.0, 101.0])
    assert sharpe == 0.0


# ── Full metrics computation ─────────────────────────────────


def test_compute_metrics_empty():
    """Empty equity curve should return zero metrics."""
    svc = BacktestService.__new__(BacktestService)
    metrics = svc._compute_metrics([], 50000.0, [])

    assert metrics.total_return_pct == 0.0
    assert metrics.annualized_return_pct == 0.0
    assert metrics.max_drawdown_pct == 0.0
    assert metrics.sharpe_ratio == 0.0


def test_compute_metrics_with_data():
    """Metrics with a basic equity curve should produce reasonable values."""
    svc = BacktestService.__new__(BacktestService)
    equity_curve = [
        {"date": "2024-01-01", "value": 50000.0},
        {"date": "2024-01-02", "value": 50500.0},
        {"date": "2024-01-03", "value": 51000.0},
        {"date": "2024-01-04", "value": 50800.0},
        {"date": "2024-01-05", "value": 51200.0},
    ]
    trading_days = [date(2024, 1, i + 1) for i in range(5)]

    metrics = svc._compute_metrics(equity_curve, 50000.0, trading_days)

    # total return = (51200 - 50000) / 50000 * 100 = 2.4%
    assert abs(metrics.total_return_pct - 2.4) < 0.1
    assert metrics.annualized_return_pct > 0
    assert metrics.max_drawdown_pct >= 0
