"""Mock news adapter — returns pre-set news items for testing/backtesting."""

from __future__ import annotations

from tradeagent.adapters.base import NewsAdapter, NewsItem


class MockNewsAdapter(NewsAdapter):
    """News adapter that returns pre-set items. Empty by default for backtests."""

    def __init__(self, items: list[NewsItem] | None = None) -> None:
        self._items = items or []

    async def query_news(
        self,
        topics: list[str],
        *,
        max_results_per_topic: int = 5,
    ) -> list[NewsItem]:
        """Return pre-set news items regardless of topics."""
        return self._items
