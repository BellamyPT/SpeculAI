"""Repository layer tests.

All tests require a running PostgreSQL instance (via docker compose up db).
Tests auto-skip when the database is unavailable thanks to the async_session fixture.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from tradeagent.core.exceptions import RepositoryError
from tradeagent.core.types import Action, PositionStatus, Side, TradeStatus
from tradeagent.repositories import (
    BenchmarkRepository,
    DecisionRepository,
    PortfolioRepository,
    StockRepository,
    TradeRepository,
)


# ────────────────────────────────────────────────────────────────────
# StockRepository
# ────────────────────────────────────────────────────────────────────


class TestStockRepository:
    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self, async_session):
        stock = await StockRepository.create(
            async_session,
            ticker="MSFT",
            name="Microsoft Corp.",
            exchange="NASDAQ",
            currency="USD",
            sector="Technology",
        )
        assert stock.id is not None
        assert stock.ticker == "MSFT"

        fetched = await StockRepository.get_by_id(async_session, stock.id)
        assert fetched is not None
        assert fetched.ticker == "MSFT"

    @pytest.mark.asyncio
    async def test_get_by_ticker(self, async_session, sample_stock):
        fetched = await StockRepository.get_by_ticker(async_session, "AAPL")
        assert fetched is not None
        assert fetched.id == sample_stock.id

    @pytest.mark.asyncio
    async def test_get_by_ticker_not_found(self, async_session):
        fetched = await StockRepository.get_by_ticker(async_session, "ZZZZ")
        assert fetched is None

    @pytest.mark.asyncio
    async def test_get_all_active(self, async_session, sample_stock):
        stocks, total = await StockRepository.get_all_active(async_session)
        assert total >= 1
        tickers = [s.ticker for s in stocks]
        assert "AAPL" in tickers

    @pytest.mark.asyncio
    async def test_get_by_sector(self, async_session, sample_stock):
        stocks, total = await StockRepository.get_by_sector(
            async_session, "Technology"
        )
        assert total >= 1
        assert stocks[0].sector == "Technology"

    @pytest.mark.asyncio
    async def test_update(self, async_session, sample_stock):
        updated = await StockRepository.update(
            async_session, sample_stock.id, name="Apple Inc. Updated"
        )
        assert updated.name == "Apple Inc. Updated"

    @pytest.mark.asyncio
    async def test_update_not_found(self, async_session):
        with pytest.raises(RepositoryError, match="not found"):
            await StockRepository.update(async_session, 999999, name="X")

    @pytest.mark.asyncio
    async def test_deactivate(self, async_session, sample_stock):
        await StockRepository.deactivate(async_session, sample_stock.id)
        fetched = await StockRepository.get_by_id(async_session, sample_stock.id)
        assert fetched is not None
        assert fetched.is_active is False

    @pytest.mark.asyncio
    async def test_bulk_upsert_prices(self, async_session, sample_stock):
        prices = [
            {
                "stock_id": sample_stock.id,
                "date": date(2024, 1, 2),
                "open": Decimal("150.00"),
                "high": Decimal("155.00"),
                "low": Decimal("149.00"),
                "close": Decimal("153.00"),
                "adj_close": Decimal("153.00"),
                "volume": 1000000,
            },
            {
                "stock_id": sample_stock.id,
                "date": date(2024, 1, 3),
                "open": Decimal("153.00"),
                "high": Decimal("156.00"),
                "low": Decimal("152.00"),
                "close": Decimal("155.00"),
                "adj_close": Decimal("155.00"),
                "volume": 1200000,
            },
        ]
        count = await StockRepository.bulk_upsert_prices(async_session, prices)
        assert count == 2

        # Upsert same dates with new close — should update, not duplicate
        prices[0]["close"] = Decimal("160.00")
        prices[0]["adj_close"] = Decimal("160.00")
        count2 = await StockRepository.bulk_upsert_prices(async_session, prices)
        assert count2 == 2

        fetched, total = await StockRepository.get_prices(
            async_session, sample_stock.id
        )
        assert total == 2
        closes = {p.date: p.close for p in fetched}
        assert closes[date(2024, 1, 2)] == Decimal("160.0000")

    @pytest.mark.asyncio
    async def test_bulk_upsert_prices_empty(self, async_session):
        count = await StockRepository.bulk_upsert_prices(async_session, [])
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_latest_price(self, async_session, sample_stock):
        prices = [
            {
                "stock_id": sample_stock.id,
                "date": date(2024, 1, 10),
                "open": Decimal("150.00"),
                "high": Decimal("155.00"),
                "low": Decimal("149.00"),
                "close": Decimal("153.00"),
                "adj_close": Decimal("153.00"),
                "volume": 1000000,
            },
            {
                "stock_id": sample_stock.id,
                "date": date(2024, 1, 11),
                "open": Decimal("153.00"),
                "high": Decimal("156.00"),
                "low": Decimal("152.00"),
                "close": Decimal("155.00"),
                "adj_close": Decimal("155.00"),
                "volume": 1200000,
            },
        ]
        await StockRepository.bulk_upsert_prices(async_session, prices)

        latest = await StockRepository.get_latest_price(
            async_session, sample_stock.id
        )
        assert latest is not None
        assert latest.date == date(2024, 1, 11)

    @pytest.mark.asyncio
    async def test_get_prices_date_filter(self, async_session, sample_stock):
        prices = [
            {
                "stock_id": sample_stock.id,
                "date": date(2024, 2, d),
                "open": Decimal("100.00"),
                "high": Decimal("101.00"),
                "low": Decimal("99.00"),
                "close": Decimal("100.50"),
                "adj_close": Decimal("100.50"),
                "volume": 500000,
            }
            for d in range(1, 6)
        ]
        await StockRepository.bulk_upsert_prices(async_session, prices)

        fetched, total = await StockRepository.get_prices(
            async_session,
            sample_stock.id,
            start_date=date(2024, 2, 2),
            end_date=date(2024, 2, 4),
        )
        assert total == 3
        assert len(fetched) == 3

    @pytest.mark.asyncio
    async def test_upsert_fundamental(self, async_session, sample_stock):
        fund = await StockRepository.upsert_fundamental(
            async_session,
            stock_id=sample_stock.id,
            snapshot_date=date(2024, 3, 1),
            pe_ratio=Decimal("28.50"),
            market_cap=Decimal("3000000000000.00"),
        )
        assert fund.pe_ratio == Decimal("28.5000")

        # Upsert same date — should update
        fund2 = await StockRepository.upsert_fundamental(
            async_session,
            stock_id=sample_stock.id,
            snapshot_date=date(2024, 3, 1),
            pe_ratio=Decimal("29.00"),
        )
        assert fund2.pe_ratio == Decimal("29.0000")

    @pytest.mark.asyncio
    async def test_get_latest_fundamental(self, async_session, sample_stock):
        await StockRepository.upsert_fundamental(
            async_session,
            stock_id=sample_stock.id,
            snapshot_date=date(2024, 3, 1),
            pe_ratio=Decimal("28.50"),
        )
        await StockRepository.upsert_fundamental(
            async_session,
            stock_id=sample_stock.id,
            snapshot_date=date(2024, 3, 15),
            pe_ratio=Decimal("30.00"),
        )

        latest = await StockRepository.get_latest_fundamental(
            async_session, sample_stock.id
        )
        assert latest is not None
        assert latest.snapshot_date == date(2024, 3, 15)


# ────────────────────────────────────────────────────────────────────
# BenchmarkRepository
# ────────────────────────────────────────────────────────────────────


class TestBenchmarkRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(self, async_session):
        bm = await BenchmarkRepository.create(
            async_session, symbol="IWDA.AS", name="iShares MSCI World"
        )
        assert bm.id is not None

        fetched = await BenchmarkRepository.get_by_id(async_session, bm.id)
        assert fetched is not None
        assert fetched.symbol == "IWDA.AS"

    @pytest.mark.asyncio
    async def test_get_by_symbol(self, async_session, sample_benchmark):
        fetched = await BenchmarkRepository.get_by_symbol(async_session, "^GSPC")
        assert fetched is not None
        assert fetched.name == "S&P 500"

    @pytest.mark.asyncio
    async def test_get_all(self, async_session, sample_benchmark):
        all_bm = await BenchmarkRepository.get_all(async_session)
        assert len(all_bm) >= 1

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, async_session, sample_benchmark):
        bm = await BenchmarkRepository.get_or_create(
            async_session, symbol="^GSPC", name="S&P 500"
        )
        assert bm.id == sample_benchmark.id

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, async_session):
        bm = await BenchmarkRepository.get_or_create(
            async_session, symbol="VWCE.DE", name="Vanguard All-World"
        )
        assert bm.id is not None
        assert bm.symbol == "VWCE.DE"

    @pytest.mark.asyncio
    async def test_bulk_upsert_prices(self, async_session, sample_benchmark):
        prices = [
            {
                "benchmark_id": sample_benchmark.id,
                "date": date(2024, 1, 2),
                "close": Decimal("4700.00"),
            },
            {
                "benchmark_id": sample_benchmark.id,
                "date": date(2024, 1, 3),
                "close": Decimal("4720.00"),
            },
        ]
        count = await BenchmarkRepository.bulk_upsert_prices(async_session, prices)
        assert count == 2

        # Upsert same dates — should update
        prices[0]["close"] = Decimal("4710.00")
        count2 = await BenchmarkRepository.bulk_upsert_prices(async_session, prices)
        assert count2 == 2

        fetched, total = await BenchmarkRepository.get_prices(
            async_session, sample_benchmark.id
        )
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_latest_price(self, async_session, sample_benchmark):
        prices = [
            {
                "benchmark_id": sample_benchmark.id,
                "date": date(2024, 4, 1),
                "close": Decimal("5000.00"),
            },
            {
                "benchmark_id": sample_benchmark.id,
                "date": date(2024, 4, 2),
                "close": Decimal("5010.00"),
            },
        ]
        await BenchmarkRepository.bulk_upsert_prices(async_session, prices)

        latest = await BenchmarkRepository.get_latest_price(
            async_session, sample_benchmark.id
        )
        assert latest is not None
        assert latest.date == date(2024, 4, 2)

    @pytest.mark.asyncio
    async def test_get_prices_date_filter(self, async_session, sample_benchmark):
        prices = [
            {
                "benchmark_id": sample_benchmark.id,
                "date": date(2024, 5, d),
                "close": Decimal("5100.00"),
            }
            for d in range(1, 6)
        ]
        await BenchmarkRepository.bulk_upsert_prices(async_session, prices)

        fetched, total = await BenchmarkRepository.get_prices(
            async_session,
            sample_benchmark.id,
            start_date=date(2024, 5, 2),
            end_date=date(2024, 5, 4),
        )
        assert total == 3


# ────────────────────────────────────────────────────────────────────
# PortfolioRepository
# ────────────────────────────────────────────────────────────────────


class TestPortfolioRepository:
    @pytest.mark.asyncio
    async def test_create_and_get_position(self, async_session, sample_stock):
        pos = await PortfolioRepository.create_position(
            async_session,
            stock_id=sample_stock.id,
            quantity=Decimal("10.000000"),
            avg_price=Decimal("150.0000"),
            currency="USD",
            opened_at=datetime(2024, 1, 15, 10, 0),
        )
        assert pos.id is not None
        assert pos.status == PositionStatus.OPEN

        fetched = await PortfolioRepository.get_position_by_id(
            async_session, pos.id
        )
        assert fetched is not None

    @pytest.mark.asyncio
    async def test_get_open_positions(self, async_session, sample_stock):
        await PortfolioRepository.create_position(
            async_session,
            stock_id=sample_stock.id,
            quantity=Decimal("5.000000"),
            avg_price=Decimal("200.0000"),
            currency="USD",
            opened_at=datetime(2024, 2, 1),
        )
        positions = await PortfolioRepository.get_open_positions(async_session)
        assert len(positions) >= 1
        assert all(p.status == PositionStatus.OPEN for p in positions)

    @pytest.mark.asyncio
    async def test_get_open_position_by_stock(self, async_session, sample_stock):
        await PortfolioRepository.create_position(
            async_session,
            stock_id=sample_stock.id,
            quantity=Decimal("5.000000"),
            avg_price=Decimal("200.0000"),
            currency="USD",
            opened_at=datetime(2024, 2, 1),
        )
        pos = await PortfolioRepository.get_open_position_by_stock(
            async_session, sample_stock.id
        )
        assert pos is not None
        assert pos.stock_id == sample_stock.id

    @pytest.mark.asyncio
    async def test_update_position(self, async_session, sample_stock):
        pos = await PortfolioRepository.create_position(
            async_session,
            stock_id=sample_stock.id,
            quantity=Decimal("10.000000"),
            avg_price=Decimal("150.0000"),
            currency="USD",
            opened_at=datetime(2024, 1, 15),
        )
        updated = await PortfolioRepository.update_position(
            async_session, pos.id, quantity=Decimal("15.000000")
        )
        assert updated.quantity == Decimal("15.000000")

    @pytest.mark.asyncio
    async def test_close_position(self, async_session, sample_stock):
        pos = await PortfolioRepository.create_position(
            async_session,
            stock_id=sample_stock.id,
            quantity=Decimal("10.000000"),
            avg_price=Decimal("150.0000"),
            currency="USD",
            opened_at=datetime(2024, 1, 15),
        )
        closed = await PortfolioRepository.close_position(
            async_session, pos.id, closed_at=datetime(2024, 2, 15)
        )
        assert closed.status == PositionStatus.CLOSED
        assert closed.closed_at == datetime(2024, 2, 15)

    @pytest.mark.asyncio
    async def test_close_position_not_found(self, async_session):
        with pytest.raises(RepositoryError, match="not found"):
            await PortfolioRepository.close_position(
                async_session, 999999, closed_at=datetime.now()
            )

    @pytest.mark.asyncio
    async def test_get_positions_history(self, async_session, sample_stock):
        pos = await PortfolioRepository.create_position(
            async_session,
            stock_id=sample_stock.id,
            quantity=Decimal("10.000000"),
            avg_price=Decimal("150.0000"),
            currency="USD",
            opened_at=datetime(2024, 1, 15),
        )
        await PortfolioRepository.close_position(
            async_session, pos.id, closed_at=datetime(2024, 2, 15)
        )

        # Include closed
        all_pos, total_all = await PortfolioRepository.get_positions_history(
            async_session, include_closed=True
        )
        assert total_all >= 1

        # Exclude closed
        open_pos, total_open = await PortfolioRepository.get_positions_history(
            async_session, include_closed=False
        )
        assert total_open == 0

    @pytest.mark.asyncio
    async def test_create_and_get_snapshot(self, async_session):
        snap = await PortfolioRepository.create_snapshot(
            async_session,
            date=date(2024, 3, 1),
            total_value=Decimal("50000.0000"),
            cash=Decimal("30000.0000"),
            invested=Decimal("20000.0000"),
            daily_pnl=Decimal("100.0000"),
            cumulative_pnl_pct=Decimal("0.2000"),
            num_positions=3,
        )
        assert snap.id is not None

        latest = await PortfolioRepository.get_latest_snapshot(async_session)
        assert latest is not None
        assert latest.date == date(2024, 3, 1)

    @pytest.mark.asyncio
    async def test_get_snapshots_date_filter(self, async_session):
        for d in range(1, 6):
            await PortfolioRepository.create_snapshot(
                async_session,
                date=date(2024, 6, d),
                total_value=Decimal("50000.0000"),
                cash=Decimal("30000.0000"),
                invested=Decimal("20000.0000"),
                daily_pnl=Decimal("0.0000"),
                cumulative_pnl_pct=Decimal("0.0000"),
                num_positions=0,
            )

        snaps, total = await PortfolioRepository.get_snapshots(
            async_session,
            start_date=date(2024, 6, 2),
            end_date=date(2024, 6, 4),
        )
        assert total == 3

    @pytest.mark.asyncio
    async def test_position_snapshots(self, async_session, sample_stock):
        port_snap = await PortfolioRepository.create_snapshot(
            async_session,
            date=date(2024, 3, 1),
            total_value=Decimal("50000.0000"),
            cash=Decimal("30000.0000"),
            invested=Decimal("20000.0000"),
            daily_pnl=Decimal("100.0000"),
            cumulative_pnl_pct=Decimal("0.2000"),
            num_positions=1,
        )

        pos_snap = await PortfolioRepository.create_position_snapshot(
            async_session,
            portfolio_snapshot_id=port_snap.id,
            stock_id=sample_stock.id,
            quantity=Decimal("10.000000"),
            market_value=Decimal("1500.0000"),
            unrealized_pnl=Decimal("50.0000"),
            weight_pct=Decimal("3.000"),
        )
        assert pos_snap.id is not None

        fetched = await PortfolioRepository.get_position_snapshots_for_portfolio(
            async_session, port_snap.id
        )
        assert len(fetched) == 1
        assert fetched[0].stock_id == sample_stock.id

    @pytest.mark.asyncio
    async def test_bulk_create_position_snapshots(self, async_session, sample_stock):
        port_snap = await PortfolioRepository.create_snapshot(
            async_session,
            date=date(2024, 3, 2),
            total_value=Decimal("50000.0000"),
            cash=Decimal("30000.0000"),
            invested=Decimal("20000.0000"),
            daily_pnl=Decimal("0.0000"),
            cumulative_pnl_pct=Decimal("0.0000"),
            num_positions=1,
        )

        snaps = await PortfolioRepository.bulk_create_position_snapshots(
            async_session,
            [
                {
                    "portfolio_snapshot_id": port_snap.id,
                    "stock_id": sample_stock.id,
                    "quantity": Decimal("10.000000"),
                    "market_value": Decimal("1500.0000"),
                    "unrealized_pnl": Decimal("50.0000"),
                    "weight_pct": Decimal("3.000"),
                }
            ],
        )
        assert len(snaps) == 1

    @pytest.mark.asyncio
    async def test_bulk_create_position_snapshots_empty(self, async_session):
        result = await PortfolioRepository.bulk_create_position_snapshots(
            async_session, []
        )
        assert result == []


# ────────────────────────────────────────────────────────────────────
# TradeRepository
# ────────────────────────────────────────────────────────────────────


class TestTradeRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(self, async_session, sample_stock):
        trade = await TradeRepository.create(
            async_session,
            stock_id=sample_stock.id,
            side=Side.BUY,
            quantity=Decimal("10.000000"),
            price=Decimal("150.0000"),
            total_value=Decimal("1500.0000"),
            currency="USD",
            status=TradeStatus.PENDING,
        )
        assert trade.id is not None
        assert trade.side == Side.BUY

        fetched = await TradeRepository.get_by_id(async_session, trade.id)
        assert fetched is not None

    @pytest.mark.asyncio
    async def test_update_status(self, async_session, sample_stock):
        trade = await TradeRepository.create(
            async_session,
            stock_id=sample_stock.id,
            side=Side.BUY,
            quantity=Decimal("10.000000"),
            price=Decimal("150.0000"),
            total_value=Decimal("1500.0000"),
            currency="USD",
            status=TradeStatus.PENDING,
        )
        now = datetime.now()
        updated = await TradeRepository.update_status(
            async_session,
            trade.id,
            TradeStatus.FILLED,
            executed_at=now,
            broker_order_id="ORD-123",
        )
        assert updated.status == TradeStatus.FILLED
        assert updated.executed_at == now
        assert updated.broker_order_id == "ORD-123"

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, async_session):
        with pytest.raises(RepositoryError, match="not found"):
            await TradeRepository.update_status(
                async_session, 999999, TradeStatus.FILLED
            )

    @pytest.mark.asyncio
    async def test_get_history_no_filters(self, async_session, sample_stock):
        await TradeRepository.create(
            async_session,
            stock_id=sample_stock.id,
            side=Side.BUY,
            quantity=Decimal("10.000000"),
            price=Decimal("150.0000"),
            total_value=Decimal("1500.0000"),
            currency="USD",
            status=TradeStatus.FILLED,
        )
        trades, total = await TradeRepository.get_history(async_session)
        assert total >= 1

    @pytest.mark.asyncio
    async def test_get_history_filter_by_ticker(self, async_session, sample_stock):
        await TradeRepository.create(
            async_session,
            stock_id=sample_stock.id,
            side=Side.BUY,
            quantity=Decimal("5.000000"),
            price=Decimal("200.0000"),
            total_value=Decimal("1000.0000"),
            currency="USD",
            status=TradeStatus.FILLED,
        )

        trades, total = await TradeRepository.get_history(
            async_session, ticker="AAPL"
        )
        assert total >= 1
        assert all(t.stock_id == sample_stock.id for t in trades)

        # Non-existent ticker
        trades2, total2 = await TradeRepository.get_history(
            async_session, ticker="ZZZZ"
        )
        assert total2 == 0

    @pytest.mark.asyncio
    async def test_get_history_filter_by_side(self, async_session, sample_stock):
        await TradeRepository.create(
            async_session,
            stock_id=sample_stock.id,
            side=Side.BUY,
            quantity=Decimal("5.000000"),
            price=Decimal("200.0000"),
            total_value=Decimal("1000.0000"),
            currency="USD",
            status=TradeStatus.FILLED,
        )

        buy_trades, buy_total = await TradeRepository.get_history(
            async_session, side=Side.BUY
        )
        assert buy_total >= 1

        sell_trades, sell_total = await TradeRepository.get_history(
            async_session, side=Side.SELL
        )
        assert sell_total == 0

    @pytest.mark.asyncio
    async def test_get_trades_by_stock(self, async_session, sample_stock):
        await TradeRepository.create(
            async_session,
            stock_id=sample_stock.id,
            side=Side.BUY,
            quantity=Decimal("10.000000"),
            price=Decimal("150.0000"),
            total_value=Decimal("1500.0000"),
            currency="USD",
            status=TradeStatus.FILLED,
        )
        trades = await TradeRepository.get_trades_by_stock(
            async_session, sample_stock.id
        )
        assert len(trades) >= 1

    @pytest.mark.asyncio
    async def test_get_trades_by_decision(self, async_session, sample_stock):
        # Create a decision report first
        report = await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.BUY,
            confidence=Decimal("0.850"),
            reasoning="Strong technicals",
            technical_summary={"rsi": 35},
            news_summary={"sentiment": "positive"},
            portfolio_state={"cash": 50000},
        )

        await TradeRepository.create(
            async_session,
            stock_id=sample_stock.id,
            side=Side.BUY,
            quantity=Decimal("10.000000"),
            price=Decimal("150.0000"),
            total_value=Decimal("1500.0000"),
            currency="USD",
            status=TradeStatus.FILLED,
            decision_report_id=report.id,
        )

        trades = await TradeRepository.get_trades_by_decision(
            async_session, report.id
        )
        assert len(trades) == 1
        assert trades[0].decision_report_id == report.id


# ────────────────────────────────────────────────────────────────────
# DecisionRepository
# ────────────────────────────────────────────────────────────────────


class TestDecisionRepository:
    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self, async_session, sample_stock):
        report = await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.BUY,
            confidence=Decimal("0.900"),
            reasoning="Bullish signals across multiple timeframes.",
            technical_summary={"rsi": 32, "macd": {"direction": "bullish"}},
            news_summary={"sentiment": "positive", "headlines": []},
            portfolio_state={"cash": 50000, "positions": 2},
        )
        assert report.id is not None
        assert report.action == Action.BUY

        fetched = await DecisionRepository.get_by_id(async_session, report.id)
        assert fetched is not None
        assert fetched.reasoning == "Bullish signals across multiple timeframes."

    @pytest.mark.asyncio
    async def test_get_list_no_filters(self, async_session, sample_stock):
        await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.HOLD,
            confidence=Decimal("0.600"),
            reasoning="Mixed signals",
            technical_summary={"rsi": 50},
            news_summary={"sentiment": "neutral"},
            portfolio_state={"cash": 40000},
        )
        reports, total = await DecisionRepository.get_list(async_session)
        assert total >= 1

    @pytest.mark.asyncio
    async def test_get_list_filter_by_action(self, async_session, sample_stock):
        await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.SELL,
            confidence=Decimal("0.750"),
            reasoning="Overbought",
            technical_summary={"rsi": 75},
            news_summary={"sentiment": "negative"},
            portfolio_state={"cash": 30000},
        )

        sells, total = await DecisionRepository.get_list(
            async_session, action=Action.SELL
        )
        assert total >= 1
        assert all(r.action == Action.SELL for r in sells)

    @pytest.mark.asyncio
    async def test_get_list_filter_by_min_confidence(
        self, async_session, sample_stock
    ):
        await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.BUY,
            confidence=Decimal("0.950"),
            reasoning="Very strong signal",
            technical_summary={"rsi": 25},
            news_summary={"sentiment": "very positive"},
            portfolio_state={"cash": 50000},
        )

        high_conf, total = await DecisionRepository.get_list(
            async_session, min_confidence=0.9
        )
        assert total >= 1
        assert all(r.confidence >= Decimal("0.900") for r in high_conf)

    @pytest.mark.asyncio
    async def test_update_outcome(self, async_session, sample_stock):
        report = await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.BUY,
            confidence=Decimal("0.800"),
            reasoning="Looks good",
            technical_summary={"rsi": 40},
            news_summary={"sentiment": "positive"},
            portfolio_state={"cash": 45000},
        )

        now = datetime.now()
        updated = await DecisionRepository.update_outcome(
            async_session,
            report.id,
            outcome_pnl=Decimal("250.0000"),
            outcome_benchmark_delta=Decimal("1.5000"),
            outcome_assessed_at=now,
        )
        assert updated.outcome_pnl == Decimal("250.0000")
        assert updated.outcome_assessed_at == now

    @pytest.mark.asyncio
    async def test_update_outcome_not_found(self, async_session):
        with pytest.raises(RepositoryError, match="not found"):
            await DecisionRepository.update_outcome(
                async_session,
                999999,
                outcome_pnl=Decimal("0"),
                outcome_benchmark_delta=Decimal("0"),
                outcome_assessed_at=datetime.now(),
            )

    @pytest.mark.asyncio
    async def test_get_unassessed(self, async_session, sample_stock):
        report = await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.BUY,
            confidence=Decimal("0.800"),
            reasoning="Promising setup",
            technical_summary={"rsi": 35},
            news_summary={"sentiment": "positive"},
            portfolio_state={"cash": 50000},
        )

        unassessed = await DecisionRepository.get_unassessed(
            async_session,
            older_than=datetime.now() + timedelta(seconds=10),
        )
        assert any(r.id == report.id for r in unassessed)

    @pytest.mark.asyncio
    async def test_context_items(self, async_session, sample_stock):
        report = await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.BUY,
            confidence=Decimal("0.800"),
            reasoning="Test",
            technical_summary={"rsi": 40},
            news_summary={"sentiment": "positive"},
            portfolio_state={"cash": 50000},
        )

        item = await DecisionRepository.create_context_item(
            async_session,
            decision_report_id=report.id,
            context_type="news",
            source="Reuters",
            content="Apple beats earnings expectations.",
            relevance_score=Decimal("0.900"),
        )
        assert item.id is not None

        # Fetch report with context items
        fetched = await DecisionRepository.get_by_id(async_session, report.id)
        assert fetched is not None
        assert len(fetched.context_items) == 1

    @pytest.mark.asyncio
    async def test_bulk_create_context_items(self, async_session, sample_stock):
        report = await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.HOLD,
            confidence=Decimal("0.500"),
            reasoning="Mixed",
            technical_summary={"rsi": 50},
            news_summary={},
            portfolio_state={"cash": 50000},
        )

        items = await DecisionRepository.bulk_create_context_items(
            async_session,
            [
                {
                    "decision_report_id": report.id,
                    "context_type": "news",
                    "source": "Bloomberg",
                    "content": "Market volatility increases.",
                },
                {
                    "decision_report_id": report.id,
                    "context_type": "technical",
                    "source": "TA engine",
                    "content": "RSI at 50, neutral.",
                },
            ],
        )
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_bulk_create_context_items_empty(self, async_session):
        result = await DecisionRepository.bulk_create_context_items(
            async_session, []
        )
        assert result == []

    # ── Memory retrieval tests ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_by_ticker(self, async_session, sample_stock):
        for i in range(3):
            await DecisionRepository.create(
                async_session,
                stock_id=sample_stock.id,
                pipeline_run_id=uuid4(),
                action=Action.BUY,
                confidence=Decimal("0.700"),
                reasoning=f"Reason {i}",
                technical_summary={"rsi": 40 + i},
                news_summary={},
                portfolio_state={"cash": 50000},
            )

        decisions = await DecisionRepository.get_by_ticker(
            async_session, sample_stock.id, limit=2
        )
        assert len(decisions) == 2

    @pytest.mark.asyncio
    async def test_get_by_sector(self, async_session, sample_stock):
        await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.BUY,
            confidence=Decimal("0.800"),
            reasoning="Sector play",
            technical_summary={"rsi": 30},
            news_summary={},
            portfolio_state={"cash": 50000},
        )

        decisions = await DecisionRepository.get_by_sector(
            async_session, "Technology"
        )
        assert len(decisions) >= 1

    @pytest.mark.asyncio
    async def test_get_by_sector_exclude_stock(self, async_session, sample_stock):
        await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.BUY,
            confidence=Decimal("0.800"),
            reasoning="Sector play",
            technical_summary={"rsi": 30},
            news_summary={},
            portfolio_state={"cash": 50000},
        )

        decisions = await DecisionRepository.get_by_sector(
            async_session,
            "Technology",
            exclude_stock_id=sample_stock.id,
        )
        assert len(decisions) == 0

    @pytest.mark.asyncio
    async def test_get_by_similar_signals(self, async_session, sample_stock):
        await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.BUY,
            confidence=Decimal("0.850"),
            reasoning="RSI match",
            technical_summary={"rsi": 35, "macd": {"direction": "bullish"}},
            news_summary={},
            portfolio_state={"cash": 50000},
        )

        # Should match rsi=35 with tolerance=10 (25-45)
        decisions = await DecisionRepository.get_by_similar_signals(
            async_session, rsi_value=30.0, rsi_tolerance=10.0
        )
        assert len(decisions) >= 1

    @pytest.mark.asyncio
    async def test_get_by_similar_signals_with_macd(
        self, async_session, sample_stock
    ):
        await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.BUY,
            confidence=Decimal("0.850"),
            reasoning="RSI+MACD match",
            technical_summary={"rsi": 35, "macd": {"direction": "bullish"}},
            news_summary={},
            portfolio_state={"cash": 50000},
        )

        # Match with macd direction filter
        decisions = await DecisionRepository.get_by_similar_signals(
            async_session,
            rsi_value=35.0,
            macd_direction="bullish",
        )
        assert len(decisions) >= 1

        # Non-matching macd direction
        decisions_miss = await DecisionRepository.get_by_similar_signals(
            async_session,
            rsi_value=35.0,
            macd_direction="bearish",
        )
        assert len(decisions_miss) == 0

    @pytest.mark.asyncio
    async def test_get_by_similar_signals_out_of_range(
        self, async_session, sample_stock
    ):
        await DecisionRepository.create(
            async_session,
            stock_id=sample_stock.id,
            pipeline_run_id=uuid4(),
            action=Action.BUY,
            confidence=Decimal("0.850"),
            reasoning="Far RSI",
            technical_summary={"rsi": 70, "macd": {"direction": "bearish"}},
            news_summary={},
            portfolio_state={"cash": 50000},
        )

        decisions = await DecisionRepository.get_by_similar_signals(
            async_session, rsi_value=30.0, rsi_tolerance=5.0
        )
        # rsi=70 is outside [25, 35]
        rsi_70_ids = [
            d.id
            for d in decisions
            if d.technical_summary.get("rsi") == 70
        ]
        assert len(rsi_70_ids) == 0
