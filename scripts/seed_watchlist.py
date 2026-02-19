#!/usr/bin/env python3
"""Seed the stock watchlist from S&P 500 + curated EU/EM tickers.

Idempotent — checks for existing tickers before creating.
Uses yfinance to look up name/exchange/currency/sector/country.

Usage:
    python scripts/seed_watchlist.py [--skip-existing] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio

from tradeagent.adapters.market_data.yfinance_adapter import YFinanceAdapter
from tradeagent.config import Settings
from tradeagent.core.logging import get_logger, setup_logging
from tradeagent.database import get_session_factory
from tradeagent.repositories.stock import StockRepository

log = get_logger(__name__)


# ── Curated ticker lists ─────────────────────────────────────────────

_EUROPEAN_LARGE_CAPS: list[str] = [
    "ASML.AS", "MC.PA", "SAP.DE", "SIE.DE", "SAN.PA",
    "AIR.PA", "OR.PA", "SU.PA", "BNP.PA", "DTE.DE",
    "ALV.DE", "INGA.AS", "PHIA.AS", "ABI.BR", "NESN.SW",
    "NOVN.SW", "ROG.SW", "UBSG.SW", "ZURN.SW", "SHEL.AS",
    "TTE.PA", "RMS.PA", "CDI.PA", "CS.PA", "BN.PA",
    "ADS.DE", "BAS.DE", "BAYN.DE", "BMW.DE", "DAI.DE",
    "MBG.DE", "MUV2.DE", "VOW3.DE", "FRE.DE", "HEN3.DE",
    "LIN.DE", "ENI.MI", "ISP.MI", "UCG.MI", "ENEL.MI",
    "ITX.MC", "IBE.MC", "SAN.MC", "TEF.MC", "BBVA.MC",
    "NOVO-B.CO", "CARL-B.CO", "MAERSK-B.CO", "VOLV-B.ST", "ERIC-B.ST",
    "ABB.ST", "SAND.ST", "SEB-A.ST", "SWED-A.ST", "AZN.L",
    "HSBA.L", "ULVR.L", "BP.L", "GSK.L", "RIO.L",
]

_EM_LARGE_CAPS: list[str] = [
    "TSM", "BABA", "TCEHY", "PDD", "JD",
    "BIDU", "NIO", "XPEV", "LI", "INFY",
    "WIT", "HDB", "IBN", "VALE", "PBR",
    "ITUB", "BBD", "NU", "ABEV", "SQM",
    "BFLY", "GRAB", "SE", "MELI", "GLOB",
    "DLO", "STNE", "PAGS", "KB", "SHG",
    "WF", "BEKE", "ZTO", "VNET", "QFIN",
    "LPL", "YMM", "TAL", "EDU", "DIDI",
]

_FALLBACK_TICKERS: list[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK-B", "UNH", "JNJ",
    "V", "WMT", "JPM", "PG", "MA",
    "ASML.AS", "SAP.DE", "TSM", "BABA", "MELI",
]


def _fetch_sp500_tickers() -> list[str]:
    """Scrape S&P 500 tickers from Wikipedia.

    Returns an empty list on failure (caller should use fallback).
    """
    try:
        import pandas as pd

        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            match="Symbol",
        )
        if tables:
            df = tables[0]
            tickers = df["Symbol"].tolist()
            # yfinance uses . instead of - for class shares (e.g. BRK.B)
            return [str(t).replace(".", "-") for t in tickers if t]
    except Exception as exc:
        log.warning("sp500_scrape_failed", error=str(exc))
    return []


def _build_ticker_list() -> list[str]:
    """Build the full de-duplicated ticker list."""
    sp500 = _fetch_sp500_tickers()
    if sp500:
        combined = sp500 + _EUROPEAN_LARGE_CAPS + _EM_LARGE_CAPS
    else:
        log.warning("using_fallback_tickers")
        combined = _FALLBACK_TICKERS + _EUROPEAN_LARGE_CAPS + _EM_LARGE_CAPS

    # De-duplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in combined:
        t_upper = t.upper()
        if t_upper not in seen:
            seen.add(t_upper)
            unique.append(t)
    return unique


async def seed_watchlist(
    settings: Settings,
    *,
    skip_existing: bool = False,
    dry_run: bool = False,
) -> None:
    """Seed the stock table with tickers and yfinance metadata."""
    tickers = _build_ticker_list()
    log.info("watchlist_candidates", count=len(tickers))

    session_factory = get_session_factory(settings)
    adapter = YFinanceAdapter()

    # Determine which tickers to process
    if skip_existing:
        async with session_factory() as session:
            existing_stocks, _ = await StockRepository.get_all_active(
                session, limit=10_000
            )
            existing_tickers = {s.ticker.upper() for s in existing_stocks}
        tickers = [t for t in tickers if t.upper() not in existing_tickers]
        log.info("tickers_after_skip", count=len(tickers), skipped=len(existing_tickers))

    if not tickers:
        log.info("no_new_tickers_to_seed")
        return

    if dry_run:
        log.info("dry_run_tickers", tickers=tickers[:20], total=len(tickers))
        return

    # Fetch fundamentals in chunks to avoid overwhelming yfinance
    chunk_size = 50
    all_snapshots = {}
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i : i + chunk_size]
        log.info("fetching_fundamentals", chunk_start=i, chunk_size=len(chunk))
        snapshots = await adapter.fetch_fundamentals(chunk)
        all_snapshots.update(snapshots)

    created = 0
    skipped = 0

    async with session_factory() as session:
        async with session.begin():
            for ticker in tickers:
                snap = all_snapshots.get(ticker)

                # Check if already exists (extra safety)
                existing = await StockRepository.get_by_ticker(session, ticker)
                if existing is not None:
                    skipped += 1
                    continue

                if snap is not None:
                    await StockRepository.create(
                        session,
                        ticker=ticker,
                        name=snap.name or ticker,
                        exchange=snap.exchange or "UNKNOWN",
                        currency=snap.currency or "USD",
                        sector=snap.sector,
                        industry=snap.industry,
                        country=snap.country,
                    )
                else:
                    # No fundamental data — create with minimal info
                    await StockRepository.create(
                        session,
                        ticker=ticker,
                        name=ticker,
                        exchange="UNKNOWN",
                        currency="USD",
                    )
                created += 1

    log.info(
        "seed_watchlist_complete",
        created=created,
        skipped=skipped,
        fundamentals_found=len(all_snapshots),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed stock watchlist")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip tickers already in the database",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print tickers without inserting",
    )
    args = parser.parse_args()

    settings = Settings.from_yaml()
    setup_logging(settings.log_level)
    asyncio.run(
        seed_watchlist(
            settings,
            skip_existing=args.skip_existing,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
