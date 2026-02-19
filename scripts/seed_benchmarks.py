#!/usr/bin/env python3
"""Seed benchmark rows and 3-year price history.

Idempotent — uses get_or_create for benchmarks and ON CONFLICT upserts
for prices. Safe to run on every container start.

Usage:
    python scripts/seed_benchmarks.py [--years N]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta

from tradeagent.adapters.market_data.yfinance_adapter import YFinanceAdapter
from tradeagent.config import Settings
from tradeagent.core.logging import get_logger, setup_logging
from tradeagent.database import get_session_factory
from tradeagent.repositories.benchmark import BenchmarkRepository

log = get_logger(__name__)


async def seed_benchmarks(settings: Settings, *, years: int = 3) -> None:
    """Seed benchmarks and their price history."""
    session_factory = get_session_factory(settings)
    adapter = YFinanceAdapter()

    end = date.today()
    start = end - timedelta(days=years * 365)

    symbols = [b.symbol for b in settings.benchmarks]

    log.info("fetching_benchmark_prices", symbols=symbols, start=str(start), end=str(end))
    price_results = await adapter.fetch_prices(symbols, start, end)

    async with session_factory() as session:
        async with session.begin():
            for bench_cfg in settings.benchmarks:
                benchmark = await BenchmarkRepository.get_or_create(
                    session,
                    symbol=bench_cfg.symbol,
                    name=bench_cfg.name,
                )

                vr = price_results.get(bench_cfg.symbol)
                if vr is None or not vr.valid_bars:
                    log.warning(
                        "no_price_data_for_benchmark",
                        symbol=bench_cfg.symbol,
                    )
                    continue

                price_dicts = [
                    {
                        "benchmark_id": benchmark.id,
                        "date": bar.date,
                        "close": bar.close,
                    }
                    for bar in vr.valid_bars
                ]

                count = await BenchmarkRepository.bulk_upsert_prices(
                    session, price_dicts
                )
                log.info(
                    "benchmark_seeded",
                    symbol=bench_cfg.symbol,
                    bars=len(price_dicts),
                    upserted=count,
                    rejected=vr.rejected_count,
                )

    log.info("seed_benchmarks_complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed benchmark price data")
    parser.add_argument(
        "--years",
        type=int,
        default=3,
        help="Number of years of history to fetch (default: 3)",
    )
    args = parser.parse_args()

    settings = Settings.from_yaml()
    setup_logging(settings.log_level)
    asyncio.run(seed_benchmarks(settings, years=args.years))


if __name__ == "__main__":
    main()
