"""Tests for SQLAlchemy model structure and Pydantic schemas.

Structure tests verify column definitions, constraints, and relationships
without requiring a database connection. DB-backed tests are skipped if
PostgreSQL is not available.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import inspect as sa_inspect

from tradeagent.models import (
    Base,
    Benchmark,
    BenchmarkPrice,
    DecisionContextItem,
    DecisionReport,
    PortfolioSnapshot,
    Position,
    PositionSnapshot,
    Stock,
    StockFundamental,
    StockPrice,
    Trade,
)
from tradeagent.schemas import (
    BenchmarkPriceResponse,
    BenchmarkResponse,
    DecisionContextItemResponse,
    DecisionReportDetailResponse,
    DecisionReportResponse,
    ErrorResponse,
    PaginatedResponse,
    PaginationMeta,
    PortfolioPerformanceResponse,
    PortfolioSnapshotResponse,
    PortfolioSummaryResponse,
    PositionResponse,
    PositionSnapshotResponse,
    StockFundamentalResponse,
    StockPriceResponse,
    StockResponse,
    TradeResponse,
)


# ---------------------------------------------------------------------------
# Model import tests
# ---------------------------------------------------------------------------
class TestModelImports:
    """Verify all 11 models + Base are importable."""

    def test_base_is_declarative_base(self):
        assert hasattr(Base, "metadata")
        assert hasattr(Base, "registry")

    def test_all_models_importable(self):
        models = [
            Stock, StockPrice, StockFundamental,
            Position, PortfolioSnapshot, PositionSnapshot,
            Trade,
            DecisionReport, DecisionContextItem,
            Benchmark, BenchmarkPrice,
        ]
        assert len(models) == 11

    def test_models_have_tablename(self):
        expected = {
            Stock: "stock",
            StockPrice: "stock_price",
            StockFundamental: "stock_fundamental",
            Position: "position",
            PortfolioSnapshot: "portfolio_snapshot",
            PositionSnapshot: "position_snapshot",
            Trade: "trade",
            DecisionReport: "decision_report",
            DecisionContextItem: "decision_context_item",
            Benchmark: "benchmark",
            BenchmarkPrice: "benchmark_price",
        }
        for model, tablename in expected.items():
            assert model.__tablename__ == tablename


# ---------------------------------------------------------------------------
# Column structure tests
# ---------------------------------------------------------------------------
def _get_columns(model):
    """Get column names from a model's table."""
    mapper = sa_inspect(model)
    return {col.key for col in mapper.columns}


class TestStockModel:
    def test_columns(self):
        cols = _get_columns(Stock)
        expected = {
            "id", "ticker", "name", "exchange", "sector", "industry",
            "country", "currency", "is_active", "created_at", "updated_at",
        }
        assert expected.issubset(cols)

    def test_ticker_unique(self):
        table = Stock.__table__
        ticker_col = table.c.ticker
        # Check unique constraint exists on ticker
        has_unique = ticker_col.unique or any(
            uc for uc in table.constraints
            if hasattr(uc, "columns") and ticker_col in uc.columns
        )
        assert has_unique


class TestStockPriceModel:
    def test_columns(self):
        cols = _get_columns(StockPrice)
        expected = {
            "id", "stock_id", "date", "open", "high", "low",
            "close", "adj_close", "volume",
        }
        assert expected.issubset(cols)

    def test_no_timestamp_columns(self):
        cols = _get_columns(StockPrice)
        assert "created_at" not in cols
        assert "updated_at" not in cols


class TestStockFundamentalModel:
    def test_columns(self):
        cols = _get_columns(StockFundamental)
        expected = {
            "id", "stock_id", "snapshot_date", "market_cap", "pe_ratio",
            "forward_pe", "peg_ratio", "price_to_book", "price_to_sales",
            "dividend_yield", "eps", "revenue_growth", "earnings_growth",
            "profit_margin", "debt_to_equity", "current_ratio", "beta",
            "next_earnings_date",
        }
        assert expected.issubset(cols)


class TestPositionModel:
    def test_columns(self):
        cols = _get_columns(Position)
        expected = {
            "id", "stock_id", "quantity", "avg_price", "currency",
            "opened_at", "closed_at", "status",
        }
        assert expected.issubset(cols)

    def test_no_timestamp_columns(self):
        cols = _get_columns(Position)
        assert "created_at" not in cols
        assert "updated_at" not in cols


class TestTradeModel:
    def test_columns(self):
        cols = _get_columns(Trade)
        expected = {
            "id", "stock_id", "decision_report_id", "side", "quantity",
            "price", "total_value", "currency", "broker_order_id",
            "status", "executed_at", "is_backtest", "backtest_run_id",
            "created_at",
        }
        assert expected.issubset(cols)

    def test_has_created_at(self):
        cols = _get_columns(Trade)
        assert "created_at" in cols


class TestDecisionReportModel:
    def test_columns(self):
        cols = _get_columns(DecisionReport)
        expected = {
            "id", "stock_id", "pipeline_run_id", "action", "confidence",
            "reasoning", "technical_summary", "news_summary",
            "memory_references", "portfolio_state", "outcome_pnl",
            "outcome_benchmark_delta", "outcome_assessed_at",
            "is_backtest", "backtest_run_id", "created_at",
        }
        assert expected.issubset(cols)

    def test_confidence_check_constraint(self):
        table = DecisionReport.__table__
        check_constraints = [
            c for c in table.constraints
            if c.__class__.__name__ == "CheckConstraint"
        ]
        assert len(check_constraints) >= 1


class TestDecisionContextItemModel:
    def test_columns(self):
        cols = _get_columns(DecisionContextItem)
        expected = {
            "id", "decision_report_id", "context_type", "source",
            "content", "relevance_score", "created_at",
        }
        assert expected.issubset(cols)


class TestPortfolioSnapshotModel:
    def test_columns(self):
        cols = _get_columns(PortfolioSnapshot)
        expected = {
            "id", "date", "total_value", "cash", "invested",
            "daily_pnl", "cumulative_pnl_pct", "num_positions",
            "is_backtest", "backtest_run_id",
        }
        assert expected.issubset(cols)


class TestPositionSnapshotModel:
    def test_columns(self):
        cols = _get_columns(PositionSnapshot)
        expected = {
            "id", "portfolio_snapshot_id", "stock_id", "quantity",
            "market_value", "unrealized_pnl", "weight_pct",
        }
        assert expected.issubset(cols)


class TestBenchmarkModel:
    def test_columns(self):
        cols = _get_columns(Benchmark)
        expected = {"id", "symbol", "name"}
        assert expected.issubset(cols)

    def test_symbol_unique(self):
        table = Benchmark.__table__
        symbol_col = table.c.symbol
        has_unique = symbol_col.unique or any(
            uc for uc in table.constraints
            if hasattr(uc, "columns") and symbol_col in uc.columns
        )
        assert has_unique


class TestBenchmarkPriceModel:
    def test_columns(self):
        cols = _get_columns(BenchmarkPrice)
        expected = {"id", "benchmark_id", "date", "close"}
        assert expected.issubset(cols)


# ---------------------------------------------------------------------------
# Foreign key tests
# ---------------------------------------------------------------------------
class TestForeignKeys:
    def _get_fk_targets(self, model):
        """Get set of FK target table.column strings for a model."""
        table = model.__table__
        return {
            f"{fk.column.table.name}.{fk.column.name}"
            for fk in table.foreign_keys
        }

    def test_stock_price_fk(self):
        assert "stock.id" in self._get_fk_targets(StockPrice)

    def test_stock_fundamental_fk(self):
        assert "stock.id" in self._get_fk_targets(StockFundamental)

    def test_position_fk(self):
        assert "stock.id" in self._get_fk_targets(Position)

    def test_trade_fks(self):
        fks = self._get_fk_targets(Trade)
        assert "stock.id" in fks
        assert "decision_report.id" in fks

    def test_decision_report_fk(self):
        assert "stock.id" in self._get_fk_targets(DecisionReport)

    def test_decision_context_item_fk(self):
        assert "decision_report.id" in self._get_fk_targets(DecisionContextItem)

    def test_portfolio_snapshot_no_fks(self):
        fks = self._get_fk_targets(PortfolioSnapshot)
        assert len(fks) == 0

    def test_position_snapshot_fks(self):
        fks = self._get_fk_targets(PositionSnapshot)
        assert "portfolio_snapshot.id" in fks
        assert "stock.id" in fks

    def test_benchmark_price_fk(self):
        assert "benchmark.id" in self._get_fk_targets(BenchmarkPrice)


# ---------------------------------------------------------------------------
# Naming convention tests
# ---------------------------------------------------------------------------
class TestNamingConvention:
    def test_metadata_has_naming_convention(self):
        nc = Base.metadata.naming_convention
        assert "pk" in nc
        assert "fk" in nc
        assert "uq" in nc
        assert "ck" in nc
        assert "ix" in nc


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------
class TestSchemaImports:
    def test_all_schemas_importable(self):
        schemas = [
            StockResponse, StockPriceResponse, StockFundamentalResponse,
            PositionResponse, PortfolioSnapshotResponse,
            PortfolioSummaryResponse, PortfolioPerformanceResponse,
            PositionSnapshotResponse,
            TradeResponse,
            DecisionReportResponse, DecisionReportDetailResponse,
            DecisionContextItemResponse,
            BenchmarkResponse, BenchmarkPriceResponse,
            PaginatedResponse, PaginationMeta, ErrorResponse,
        ]
        assert len(schemas) == 17


class TestSchemaFromAttributes:
    def test_stock_response_from_attributes(self):
        assert StockResponse.model_config.get("from_attributes") is True

    def test_trade_response_from_attributes(self):
        assert TradeResponse.model_config.get("from_attributes") is True

    def test_decision_report_response_from_attributes(self):
        assert DecisionReportResponse.model_config.get("from_attributes") is True

    def test_benchmark_response_from_attributes(self):
        assert BenchmarkResponse.model_config.get("from_attributes") is True


class TestSchemaValidation:
    def test_error_response_construction(self):
        resp = ErrorResponse(
            error={
                "code": "VALIDATION_ERROR",
                "message": "Invalid input",
                "details": [{"field": "ticker", "issue": "Required"}],
            }
        )
        assert resp.error.code == "VALIDATION_ERROR"
        assert len(resp.error.details) == 1

    def test_pagination_meta(self):
        meta = PaginationMeta(total=100, limit=50, offset=0, has_more=True)
        assert meta.has_more is True

    def test_stock_response_fields(self):
        data = {
            "id": 1,
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "US",
            "currency": "USD",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        resp = StockResponse(**data)
        assert resp.ticker == "AAPL"

    def test_trade_response_nullable_fields(self):
        data = {
            "id": 1,
            "stock_id": 1,
            "decision_report_id": None,
            "side": "BUY",
            "quantity": Decimal("10.5"),
            "price": Decimal("150.25"),
            "total_value": Decimal("1577.63"),
            "currency": "USD",
            "broker_order_id": None,
            "status": "FILLED",
            "executed_at": None,
            "is_backtest": False,
            "backtest_run_id": None,
            "created_at": datetime.now(),
        }
        resp = TradeResponse(**data)
        assert resp.decision_report_id is None
        assert resp.broker_order_id is None

    def test_decision_report_detail_with_context_items(self):
        data = {
            "id": 1,
            "stock_id": 1,
            "pipeline_run_id": uuid4(),
            "action": "BUY",
            "confidence": Decimal("0.85"),
            "reasoning": "Strong fundamentals",
            "technical_summary": {"rsi": 35},
            "news_summary": {"sentiment": "positive"},
            "memory_references": None,
            "portfolio_state": {"cash": 50000},
            "outcome_pnl": None,
            "outcome_benchmark_delta": None,
            "outcome_assessed_at": None,
            "is_backtest": False,
            "backtest_run_id": None,
            "created_at": datetime.now(),
            "context_items": [
                {
                    "id": 1,
                    "decision_report_id": 1,
                    "context_type": "news",
                    "source": "Reuters",
                    "content": "Apple releases new product",
                    "relevance_score": Decimal("0.9"),
                    "created_at": datetime.now(),
                }
            ],
        }
        resp = DecisionReportDetailResponse(**data)
        assert len(resp.context_items) == 1
        assert resp.context_items[0].context_type == "news"


# ---------------------------------------------------------------------------
# Config property test
# ---------------------------------------------------------------------------
class TestConfigDatabaseUrlAsync:
    def test_async_url_conversion(self, settings):
        assert settings.database_url.startswith("postgresql://")
        assert settings.database_url_async.startswith("postgresql+asyncpg://")

    def test_async_url_preserves_path(self, settings):
        sync = settings.database_url.replace("postgresql://", "")
        async_ = settings.database_url_async.replace("postgresql+asyncpg://", "")
        assert sync == async_
