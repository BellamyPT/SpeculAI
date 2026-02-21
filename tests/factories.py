"""factory_boy factories for all TradeAgent models."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import factory

from tradeagent.models.benchmark import Benchmark, BenchmarkPrice
from tradeagent.models.decision import DecisionContextItem, DecisionReport
from tradeagent.models.portfolio import PortfolioSnapshot, Position, PositionSnapshot
from tradeagent.models.stock import Stock, StockFundamental, StockPrice
from tradeagent.models.trade import Trade


class StockFactory(factory.Factory):
    class Meta:
        model = Stock

    ticker = factory.Sequence(lambda n: f"TICK{n}")
    name = factory.Faker("company")
    exchange = "NASDAQ"
    currency = "USD"
    sector = "Technology"
    industry = "Software"
    country = "US"
    is_active = True


class StockPriceFactory(factory.Factory):
    class Meta:
        model = StockPrice

    stock_id = 1
    date = factory.LazyFunction(date.today)
    open = Decimal("150.00")
    high = Decimal("155.00")
    low = Decimal("148.00")
    close = Decimal("152.00")
    adj_close = Decimal("152.00")
    volume = 1_000_000


class StockFundamentalFactory(factory.Factory):
    class Meta:
        model = StockFundamental

    stock_id = 1
    snapshot_date = factory.LazyFunction(date.today)
    market_cap = Decimal("3000000000000")
    pe_ratio = Decimal("28.5")
    forward_pe = Decimal("25.0")
    dividend_yield = Decimal("0.006")
    eps = Decimal("6.50")
    beta = Decimal("1.2")


class PositionFactory(factory.Factory):
    class Meta:
        model = Position

    stock_id = 1
    quantity = Decimal("10.000000")
    avg_price = Decimal("145.0000")
    currency = "USD"
    status = "OPEN"
    opened_at = factory.LazyFunction(lambda: datetime.now(tz=timezone.utc))


class TradeFactory(factory.Factory):
    class Meta:
        model = Trade

    stock_id = 1
    side = "BUY"
    quantity = Decimal("5.000000")
    price = Decimal("152.0000")
    total_value = Decimal("760.0000")
    currency = "USD"
    status = "FILLED"
    executed_at = factory.LazyFunction(lambda: datetime.now(tz=timezone.utc))
    is_backtest = False


class DecisionReportFactory(factory.Factory):
    class Meta:
        model = DecisionReport

    stock_id = 1
    pipeline_run_id = factory.LazyFunction(lambda: __import__("uuid").uuid4())
    action = "BUY"
    confidence = Decimal("0.80")
    reasoning = "Strong technical signals with bullish momentum"
    technical_summary = factory.LazyFunction(lambda: {"rsi": 45.0, "macd": {"direction": "bullish"}})
    news_summary = factory.LazyFunction(dict)
    portfolio_state = factory.LazyFunction(lambda: {"total_value": "50000", "cash_available": "40000"})
    is_backtest = False


class DecisionContextItemFactory(factory.Factory):
    class Meta:
        model = DecisionContextItem

    decision_report_id = 1
    context_type = "technical"
    source = "indicators:AAPL"
    content = '{"rsi": 45.0}'


class PortfolioSnapshotFactory(factory.Factory):
    class Meta:
        model = PortfolioSnapshot

    date = factory.LazyFunction(date.today)
    total_value = Decimal("50000.0000")
    cash = Decimal("40000.0000")
    invested = Decimal("10000.0000")
    daily_pnl = Decimal("150.0000")
    cumulative_pnl_pct = Decimal("0.3000")
    num_positions = 2
    is_backtest = False


class PositionSnapshotFactory(factory.Factory):
    class Meta:
        model = PositionSnapshot

    portfolio_snapshot_id = 1
    stock_id = 1
    quantity = Decimal("10.000000")
    market_value = Decimal("1520.0000")
    unrealized_pnl = Decimal("70.0000")
    weight_pct = Decimal("3.040")


class BenchmarkFactory(factory.Factory):
    class Meta:
        model = Benchmark

    symbol = factory.Sequence(lambda n: f"^BENCH{n}")
    name = factory.Sequence(lambda n: f"Benchmark {n}")


class BenchmarkPriceFactory(factory.Factory):
    class Meta:
        model = BenchmarkPrice

    benchmark_id = 1
    date = factory.LazyFunction(date.today)
    close = Decimal("4500.0000")
