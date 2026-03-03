"""remove backtest columns

Revision ID: 002
Revises: 001
Create Date: 2026-03-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop conditional index on portfolio_snapshot
    op.drop_index("ix_portfolio_snapshot_date_live", table_name="portfolio_snapshot")

    # Drop backtest columns from trade
    op.drop_column("trade", "is_backtest")
    op.drop_column("trade", "backtest_run_id")

    # Drop backtest columns from decision_report
    op.drop_column("decision_report", "is_backtest")
    op.drop_column("decision_report", "backtest_run_id")

    # Drop backtest columns from portfolio_snapshot
    op.drop_column("portfolio_snapshot", "is_backtest")
    op.drop_column("portfolio_snapshot", "backtest_run_id")

    # Create simple unique index on portfolio_snapshot.date
    op.create_unique_constraint(
        "uq_portfolio_snapshot_date", "portfolio_snapshot", ["date"]
    )


def downgrade() -> None:
    # Drop the simple unique constraint
    op.drop_constraint("uq_portfolio_snapshot_date", "portfolio_snapshot", type_="unique")

    # Re-add backtest columns to portfolio_snapshot
    op.add_column(
        "portfolio_snapshot",
        sa.Column("is_backtest", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "portfolio_snapshot",
        sa.Column("backtest_run_id", sa.Uuid(), nullable=True),
    )

    # Re-add backtest columns to decision_report
    op.add_column(
        "decision_report",
        sa.Column("is_backtest", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "decision_report",
        sa.Column("backtest_run_id", sa.Uuid(), nullable=True),
    )

    # Re-add backtest columns to trade
    op.add_column(
        "trade",
        sa.Column("is_backtest", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "trade",
        sa.Column("backtest_run_id", sa.Uuid(), nullable=True),
    )

    # Re-create conditional index
    op.create_index(
        "ix_portfolio_snapshot_date_live",
        "portfolio_snapshot",
        ["date"],
        unique=True,
        postgresql_where=sa.text("is_backtest = FALSE"),
    )
