"""Perplexity API adapter for financial news retrieval."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from tradeagent.adapters.base import NewsAdapter, NewsItem
from tradeagent.core.logging import get_logger

log = get_logger(__name__)

_API_URL = "https://api.perplexity.ai/chat/completions"


class PerplexityNewsAdapter(NewsAdapter):
    """Fetch financial news summaries via the Perplexity Sonar API.

    Returns an empty list on total failure — never raises.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "sonar",
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ── Public API ───────────────────────────────────────────────────

    async def query_news(
        self,
        topics: list[str],
        *,
        max_results_per_topic: int = 5,
    ) -> list[NewsItem]:
        """Query news for each topic. Returns flat deduplicated list."""
        if not topics:
            return []

        client = self._get_client()
        all_items: list[NewsItem] = []
        seen_urls: set[str] = set()

        for topic in topics:
            try:
                items = await self._query_single_topic(
                    client, topic, max_results_per_topic
                )
                for item in items:
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        all_items.append(item)
            except Exception:
                log.warning("news_topic_query_failed", topic=topic, exc_info=True)

        return all_items

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Private methods ──────────────────────────────────────────────

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def _query_single_topic(
        self,
        client: httpx.AsyncClient,
        topic: str,
        max_results: int,
    ) -> list[NewsItem]:
        """Query a single topic with retry."""
        prompt = self._build_prompt(topic, max_results)
        response_data = await self._call_perplexity(client, prompt)
        return self._parse_response(topic, response_data)

    async def _call_perplexity(
        self,
        client: httpx.AsyncClient,
        prompt: str,
    ) -> dict:
        """POST to Perplexity API with retry on failure (2s, 4s backoff)."""
        backoff_delays = [2.0, 4.0]
        last_error: Exception | None = None

        for attempt in range(len(backoff_delays) + 1):
            try:
                response = await client.post(
                    _API_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt,
                            }
                        ],
                    },
                )
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                log.warning(
                    "perplexity_api_error",
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt < len(backoff_delays):
                    await asyncio.sleep(backoff_delays[attempt])

        raise last_error  # type: ignore[misc]

    def _parse_response(self, topic: str, response_data: dict) -> list[NewsItem]:
        """Parse Perplexity chat completion response and citations into NewsItems."""
        items: list[NewsItem] = []

        choices = response_data.get("choices", [])
        if not choices:
            return items

        message = choices[0].get("message", {})
        content = message.get("content", "")
        citations = response_data.get("citations", [])

        # Each citation becomes a NewsItem
        if citations:
            for i, url in enumerate(citations):
                if not isinstance(url, str):
                    continue
                items.append(
                    NewsItem(
                        source="perplexity",
                        headline=f"{topic} - source {i + 1}",
                        summary=content[:500] if i == 0 else "",
                        published_at=datetime.now(tz=timezone.utc),
                        url=url,
                        relevance_score=None,
                    )
                )
        elif content:
            # No citations — wrap the whole response as a single item
            items.append(
                NewsItem(
                    source="perplexity",
                    headline=topic,
                    summary=content[:500],
                    published_at=datetime.now(tz=timezone.utc),
                    url="",
                    relevance_score=None,
                )
            )

        return items

    @staticmethod
    def _build_prompt(topic: str, max_results: int) -> str:
        return (
            f"Provide the {max_results} most important recent financial news "
            f"headlines and brief summaries about: {topic}. "
            f"Focus on market-moving events, earnings, regulatory changes, "
            f"and significant analyst upgrades/downgrades. "
            f"Be concise and factual."
        )
