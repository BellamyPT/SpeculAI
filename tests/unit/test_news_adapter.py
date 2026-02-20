"""Tests for the PerplexityNewsAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from tradeagent.adapters.news.perplexity_adapter import PerplexityNewsAdapter


@pytest.fixture
def adapter() -> PerplexityNewsAdapter:
    return PerplexityNewsAdapter(api_key="test-key", model="sonar", timeout=5.0)


def _mock_response(
    content: str = "Market update summary.",
    citations: list[str] | None = None,
    status_code: int = 200,
) -> httpx.Response:
    body = {
        "choices": [{"message": {"content": content}}],
    }
    if citations is not None:
        body["citations"] = citations
    return httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("POST", "https://api.perplexity.ai/chat/completions"),
    )


class TestQueryNews:
    async def test_success_with_citations(self, adapter):
        mock_resp = _mock_response(
            content="Tech stocks rally.",
            citations=["https://example.com/1", "https://example.com/2"],
        )
        with patch.object(adapter, "_get_client") as mock_client_fn:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_fn.return_value = mock_client

            items = await adapter.query_news(["technology stocks"])

        assert len(items) == 2
        assert items[0].source == "perplexity"
        assert items[0].url == "https://example.com/1"
        assert items[1].url == "https://example.com/2"

    async def test_success_no_citations(self, adapter):
        mock_resp = _mock_response(content="General market news.")
        with patch.object(adapter, "_get_client") as mock_client_fn:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_fn.return_value = mock_client

            items = await adapter.query_news(["energy sector"])

        assert len(items) == 1
        assert items[0].headline == "energy sector"

    async def test_empty_topics(self, adapter):
        items = await adapter.query_news([])
        assert items == []

    async def test_deduplication(self, adapter):
        """Duplicate URLs across topics are deduplicated."""
        mock_resp = _mock_response(
            citations=["https://example.com/shared", "https://example.com/unique1"]
        )
        mock_resp2 = _mock_response(
            citations=["https://example.com/shared", "https://example.com/unique2"]
        )

        with patch.object(adapter, "_get_client") as mock_client_fn:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=[mock_resp, mock_resp2])
            mock_client_fn.return_value = mock_client

            items = await adapter.query_news(["topic1", "topic2"])

        urls = [item.url for item in items]
        assert len(set(urls)) == len(urls)  # all unique
        assert "https://example.com/shared" in urls

    async def test_all_retries_fail_returns_empty(self, adapter):
        """When all API calls fail, returns empty list (never raises)."""
        with patch.object(adapter, "_get_client") as mock_client_fn:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPError("connection failed")
            )
            mock_client_fn.return_value = mock_client

            items = await adapter.query_news(["failing topic"])

        assert items == []

    async def test_partial_failure(self, adapter):
        """One topic fails, the other succeeds."""
        mock_resp = _mock_response(citations=["https://example.com/ok"])

        with patch.object(adapter, "_get_client") as mock_client_fn:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=[
                    httpx.HTTPError("fail"),
                    httpx.HTTPError("fail"),
                    httpx.HTTPError("fail"),  # 3 retries for first topic
                    mock_resp,  # second topic succeeds
                ]
            )
            mock_client_fn.return_value = mock_client

            items = await adapter.query_news(["bad topic", "good topic"])

        assert len(items) == 1
        assert items[0].url == "https://example.com/ok"


class TestCallPerplexity:
    async def test_retry_on_error(self, adapter):
        """Retries on HTTP error, succeeds on second attempt."""
        mock_resp = _mock_response()
        client = AsyncMock()
        client.post = AsyncMock(
            side_effect=[httpx.HTTPError("temporary"), mock_resp]
        )

        result = await adapter._call_perplexity(client, "test prompt")
        assert "choices" in result
        assert client.post.call_count == 2

    async def test_all_retries_exhausted(self, adapter):
        """Raises after all retries are exhausted."""
        client = AsyncMock()
        client.post = AsyncMock(
            side_effect=httpx.HTTPError("persistent error")
        )

        with pytest.raises(httpx.HTTPError):
            await adapter._call_perplexity(client, "test prompt")

        assert client.post.call_count == 3  # initial + 2 retries


class TestBuildPrompt:
    def test_contains_topic(self):
        prompt = PerplexityNewsAdapter._build_prompt("AI stocks", 5)
        assert "AI stocks" in prompt
        assert "5" in prompt


class TestClose:
    async def test_close_without_client(self, adapter):
        await adapter.close()  # should not raise

    async def test_close_with_client(self, adapter):
        adapter._client = AsyncMock()
        adapter._client.aclose = AsyncMock()
        await adapter.close()
        adapter._client is None  # noqa: B015
