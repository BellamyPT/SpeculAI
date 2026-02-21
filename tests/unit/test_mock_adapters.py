"""Unit tests for mock adapters (LLM, MarketData, News)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from tradeagent.adapters.base import FundamentalSnapshot, NewsItem, PriceBar
from tradeagent.adapters.llm.mock_llm import MockLLMAdapter
from tradeagent.adapters.market_data.mock_market_data import MockMarketDataAdapter
from tradeagent.adapters.news.mock_news import MockNewsAdapter


# ── MockMarketDataAdapter ────────────────────────────────────


def _make_bars(ticker: str) -> list[PriceBar]:
    """Create 5 price bars for testing."""
    bars = []
    for i in range(5):
        d = date(2024, 1, i + 1) if i < 4 else date(2024, 1, 5)
        bars.append(
            PriceBar(
                ticker=ticker,
                date=d,
                open=Decimal("100") + Decimal(str(i)),
                high=Decimal("105") + Decimal(str(i)),
                low=Decimal("95") + Decimal(str(i)),
                close=Decimal("102") + Decimal(str(i)),
                adj_close=Decimal("102") + Decimal(str(i)),
                volume=1_000_000,
            )
        )
    return bars


async def test_mock_market_data_filters_by_date():
    """fetch_prices should filter bars to the requested date range."""
    adapter = MockMarketDataAdapter()
    adapter.load_prices({"AAPL": _make_bars("AAPL")})

    # Only request Jan 1-3
    results = await adapter.fetch_prices(
        ["AAPL"], date(2024, 1, 1), date(2024, 1, 3)
    )

    assert "AAPL" in results
    bars = results["AAPL"].valid_bars
    assert all(b.date >= date(2024, 1, 1) for b in bars)
    assert all(b.date <= date(2024, 1, 3) for b in bars)


async def test_mock_market_data_no_lookahead():
    """Requesting a date range should not return future bars."""
    adapter = MockMarketDataAdapter()
    adapter.load_prices({"AAPL": _make_bars("AAPL")})

    results = await adapter.fetch_prices(
        ["AAPL"], date(2024, 1, 1), date(2024, 1, 2)
    )

    bars = results["AAPL"].valid_bars
    for bar in bars:
        assert bar.date <= date(2024, 1, 2)


async def test_mock_market_data_missing_ticker():
    """Requesting a ticker not loaded should return empty bars."""
    adapter = MockMarketDataAdapter()
    adapter.load_prices({"AAPL": _make_bars("AAPL")})

    results = await adapter.fetch_prices(
        ["MSFT"], date(2024, 1, 1), date(2024, 1, 5)
    )

    assert "MSFT" in results
    assert len(results["MSFT"].valid_bars) == 0


async def test_mock_market_data_fundamentals():
    """fetch_fundamentals should return pre-loaded data."""
    adapter = MockMarketDataAdapter()
    fund = FundamentalSnapshot(
        ticker="AAPL",
        snapshot_date=date.today(),
        market_cap=Decimal("3000000000000"),
        pe_ratio=Decimal("28.5"),
    )
    adapter.load_fundamentals({"AAPL": fund})

    result = await adapter.fetch_fundamentals(["AAPL", "MSFT"])

    assert "AAPL" in result
    assert result["AAPL"].pe_ratio == Decimal("28.5")
    assert "MSFT" not in result


# ── MockLLMAdapter ───────────────────────────────────────────


async def test_mock_llm_default_response():
    """Default response should produce BUY for the first candidate."""
    adapter = MockLLMAdapter()

    result = await adapter.analyze({
        "candidates": [
            {"ticker": "AAPL"},
            {"ticker": "MSFT"},
        ],
        "portfolio_state": {},
    })

    assert result.parse_success is True
    recommendations = result.parsed.get("recommendations", [])
    assert len(recommendations) >= 1
    assert recommendations[0]["ticker"] == "AAPL"
    assert recommendations[0]["action"] == "BUY"


async def test_mock_llm_set_response():
    """set_response should override the default response."""
    adapter = MockLLMAdapter()
    custom = {"recommendations": [{"ticker": "TSLA", "action": "SELL", "confidence": 0.9}]}
    adapter.set_response(custom)

    result = await adapter.analyze({"candidates": []})

    assert result.parsed == custom
    assert result.parse_success is True


async def test_mock_llm_empty_candidates():
    """With no candidates, default should return empty recommendations."""
    adapter = MockLLMAdapter()

    result = await adapter.analyze({"candidates": []})

    recommendations = result.parsed.get("recommendations", [])
    assert len(recommendations) == 0


async def test_mock_llm_token_count():
    """Response should include a token count."""
    adapter = MockLLMAdapter()

    result = await adapter.analyze({"candidates": [{"ticker": "AAPL"}]})

    assert result.token_count > 0
    assert result.response_time_seconds >= 0


# ── MockNewsAdapter ──────────────────────────────────────────


async def test_mock_news_empty_default():
    """Default MockNewsAdapter should return empty list."""
    adapter = MockNewsAdapter()

    items = await adapter.query_news(["technology", "AI"])

    assert items == []


async def test_mock_news_with_items():
    """Pre-set items should be returned regardless of topics."""
    news = [
        NewsItem(
            source="Reuters",
            headline="Tech rally continues",
            summary="Markets are up",
            published_at=None,
            url="https://example.com",
        ),
    ]
    adapter = MockNewsAdapter(items=news)

    result = await adapter.query_news(["unrelated topic"])

    assert len(result) == 1
    assert result[0].headline == "Tech rally continues"
