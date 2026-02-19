"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # stock
    op.create_table(
        "stock",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("country", sa.String(50), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock")),
        sa.UniqueConstraint("ticker", name=op.f("uq_stock_ticker")),
    )

    # stock_price
    op.create_table(
        "stock_price",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=False),
        sa.Column("high", sa.Numeric(12, 4), nullable=False),
        sa.Column("low", sa.Numeric(12, 4), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("adj_close", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_price")),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"], name=op.f("fk_stock_price_stock_id_stock")),
        sa.UniqueConstraint("stock_id", "date", name=op.f("uq_stock_price_stock_id")),
    )
    op.create_index(
        "ix_stock_price_stock_id_date_desc",
        "stock_price",
        ["stock_id", "date"],
    )

    # stock_fundamental
    op.create_table(
        "stock_fundamental",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("market_cap", sa.Numeric(18, 2), nullable=True),
        sa.Column("pe_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("forward_pe", sa.Numeric(10, 4), nullable=True),
        sa.Column("peg_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("price_to_book", sa.Numeric(10, 4), nullable=True),
        sa.Column("price_to_sales", sa.Numeric(10, 4), nullable=True),
        sa.Column("dividend_yield", sa.Numeric(8, 6), nullable=True),
        sa.Column("eps", sa.Numeric(10, 4), nullable=True),
        sa.Column("revenue_growth", sa.Numeric(8, 4), nullable=True),
        sa.Column("earnings_growth", sa.Numeric(8, 4), nullable=True),
        sa.Column("profit_margin", sa.Numeric(8, 4), nullable=True),
        sa.Column("debt_to_equity", sa.Numeric(10, 4), nullable=True),
        sa.Column("current_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("beta", sa.Numeric(6, 4), nullable=True),
        sa.Column("next_earnings_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_fundamental")),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"], name=op.f("fk_stock_fundamental_stock_id_stock")),
        sa.UniqueConstraint("stock_id", "snapshot_date", name=op.f("uq_stock_fundamental_stock_id")),
    )

    # benchmark
    op.create_table(
        "benchmark",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_benchmark")),
        sa.UniqueConstraint("symbol", name=op.f("uq_benchmark_symbol")),
    )

    # benchmark_price
    op.create_table(
        "benchmark_price",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("benchmark_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_benchmark_price")),
        sa.ForeignKeyConstraint(["benchmark_id"], ["benchmark.id"], name=op.f("fk_benchmark_price_benchmark_id_benchmark")),
        sa.UniqueConstraint("benchmark_id", "date", name=op.f("uq_benchmark_price_benchmark_id")),
    )

    # decision_report
    op.create_table(
        "decision_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("pipeline_run_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("technical_summary", postgresql.JSONB(), nullable=False),
        sa.Column("news_summary", postgresql.JSONB(), nullable=False),
        sa.Column("memory_references", postgresql.JSONB(), nullable=True),
        sa.Column("portfolio_state", postgresql.JSONB(), nullable=False),
        sa.Column("outcome_pnl", sa.Numeric(12, 4), nullable=True),
        sa.Column("outcome_benchmark_delta", sa.Numeric(8, 4), nullable=True),
        sa.Column("outcome_assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_backtest", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("backtest_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_report")),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"], name=op.f("fk_decision_report_stock_id_stock")),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name=op.f("ck_decision_report_confidence_range")),
    )

    # decision_context_item
    op.create_table(
        "decision_context_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("decision_report_id", sa.Integer(), nullable=False),
        sa.Column("context_type", sa.String(30), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("relevance_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_context_item")),
        sa.ForeignKeyConstraint(
            ["decision_report_id"], ["decision_report.id"],
            name=op.f("fk_decision_context_item_decision_report_id_decision_report"),
        ),
    )

    # position
    op.create_table(
        "position",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 6), nullable=False),
        sa.Column("avg_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), server_default="OPEN", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_position")),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"], name=op.f("fk_position_stock_id_stock")),
    )
    op.create_index(
        "ix_position_status_open",
        "position",
        ["stock_id"],
        postgresql_where=sa.text("status = 'OPEN'"),
    )

    # trade
    op.create_table(
        "trade",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("decision_report_id", sa.Integer(), nullable=True),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 6), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("total_value", sa.Numeric(14, 4), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("broker_order_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_backtest", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("backtest_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trade")),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"], name=op.f("fk_trade_stock_id_stock")),
        sa.ForeignKeyConstraint(
            ["decision_report_id"], ["decision_report.id"],
            name=op.f("fk_trade_decision_report_id_decision_report"),
        ),
    )

    # portfolio_snapshot
    op.create_table(
        "portfolio_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("total_value", sa.Numeric(14, 4), nullable=False),
        sa.Column("cash", sa.Numeric(14, 4), nullable=False),
        sa.Column("invested", sa.Numeric(14, 4), nullable=False),
        sa.Column("daily_pnl", sa.Numeric(12, 4), nullable=False),
        sa.Column("cumulative_pnl_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("num_positions", sa.Integer(), nullable=False),
        sa.Column("is_backtest", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("backtest_run_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolio_snapshot")),
    )
    op.create_index(
        "ix_portfolio_snapshot_date_live",
        "portfolio_snapshot",
        ["date"],
        unique=True,
        postgresql_where=sa.text("is_backtest = FALSE"),
    )

    # position_snapshot
    op.create_table(
        "position_snapshot",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("portfolio_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 6), nullable=False),
        sa.Column("market_value", sa.Numeric(14, 4), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(12, 4), nullable=False),
        sa.Column("weight_pct", sa.Numeric(6, 3), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_position_snapshot")),
        sa.ForeignKeyConstraint(
            ["portfolio_snapshot_id"], ["portfolio_snapshot.id"],
            name=op.f("fk_position_snapshot_portfolio_snapshot_id_portfolio_snapshot"),
        ),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"], name=op.f("fk_position_snapshot_stock_id_stock")),
    )


def downgrade() -> None:
    op.drop_table("position_snapshot")
    op.drop_index("ix_portfolio_snapshot_date_live", table_name="portfolio_snapshot")
    op.drop_table("portfolio_snapshot")
    op.drop_table("trade")
    op.drop_index("ix_position_status_open", table_name="position")
    op.drop_table("position")
    op.drop_table("decision_context_item")
    op.drop_table("decision_report")
    op.drop_table("benchmark_price")
    op.drop_table("benchmark")
    op.drop_index("ix_stock_price_stock_id_date_desc", table_name="stock_price")
    op.drop_table("stock_fundamental")
    op.drop_table("stock_price")
    op.drop_table("stock")
