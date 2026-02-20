"""Tests for the ClaudeCLIAdapter."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tradeagent.adapters.llm.claude_cli import ClaudeCLIAdapter
from tradeagent.core.exceptions import LLMError


@pytest.fixture
def adapter() -> ClaudeCLIAdapter:
    return ClaudeCLIAdapter(
        cli_path="claude",
        timeout_seconds=10,
        max_retries=3,
    )


def _mock_process(stdout: str = "", returncode: int = 0) -> AsyncMock:
    proc = AsyncMock()
    proc.communicate = AsyncMock(
        return_value=(stdout.encode(), b"")
    )
    proc.returncode = returncode
    return proc


class TestAnalyze:
    async def test_success(self, adapter):
        json_response = '{"recommendations": [], "market_outlook": "stable"}'
        proc = _mock_process(stdout=json_response)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with patch("asyncio.wait_for", return_value=(json_response.encode(), b"")):
                proc.communicate = AsyncMock(
                    return_value=(json_response.encode(), b"")
                )
                result = await adapter.analyze({"portfolio_state": {}})

        assert result.parse_success is True
        assert result.parsed["recommendations"] == []
        assert result.response_time_seconds >= 0

    async def test_json_extraction_from_wrapped_text(self, adapter):
        """CLI may return text around the JSON."""
        text = 'Here is my analysis:\n{"recommendations": [{"ticker": "AAPL"}]}\nDone.'
        proc = _mock_process(stdout=text)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await adapter.analyze({"candidates": []})

        assert result.parse_success is True
        assert result.parsed["recommendations"][0]["ticker"] == "AAPL"

    async def test_retry_on_parse_failure(self, adapter):
        """Retries when JSON parsing fails, then succeeds."""
        bad_output = "This is not JSON at all"
        good_output = '{"action": "BUY"}'

        proc_bad = _mock_process(stdout=bad_output)
        proc_good = _mock_process(stdout=good_output)

        call_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return proc_bad if call_count <= 1 else proc_good

        with patch("asyncio.create_subprocess_exec", side_effect=mock_create):
            result = await adapter.analyze({"portfolio_state": {}})

        assert result.parse_success is True
        assert result.parsed["action"] == "BUY"

    async def test_all_retries_fail(self, adapter):
        """Raises LLMError after all retries fail to parse."""
        proc = _mock_process(stdout="not json")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(LLMError, match="Failed to parse"):
                await adapter.analyze({"portfolio_state": {}})


class TestInvokeCLI:
    async def test_cli_not_found(self, adapter):
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("not found"),
        ):
            with pytest.raises(LLMError, match="not found"):
                await adapter._invoke_cli("test prompt")

    async def test_timeout(self, adapter):
        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(LLMError, match="timed out"):
                await adapter._invoke_cli("test prompt")

    async def test_non_zero_exit(self, adapter):
        proc = _mock_process(stdout="error", returncode=1)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(LLMError, match="exited with code 1"):
                await adapter._invoke_cli("test prompt")

    async def test_empty_stdout(self, adapter):
        proc = _mock_process(stdout="")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(LLMError, match="empty output"):
                await adapter._invoke_cli("test prompt")


class TestExtractJSON:
    def test_valid_json(self):
        result = ClaudeCLIAdapter._extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_text(self):
        result = ClaudeCLIAdapter._extract_json('prefix {"a": 1} suffix')
        assert result == {"a": 1}

    def test_no_json(self):
        with pytest.raises(ValueError, match="No JSON"):
            ClaudeCLIAdapter._extract_json("no json here")

    def test_invalid_json(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            ClaudeCLIAdapter._extract_json("{invalid json}")

    def test_nested_json(self):
        result = ClaudeCLIAdapter._extract_json(
            '{"outer": {"inner": [1, 2, 3]}}'
        )
        assert result["outer"]["inner"] == [1, 2, 3]


class TestBuildAnalysisPrompt:
    def test_includes_portfolio(self):
        prompt = ClaudeCLIAdapter.build_analysis_prompt(
            {"portfolio_state": {"total_value": 50000, "cash_available": 10000}}
        )
        assert "Portfolio State" in prompt
        assert "50000" in prompt

    def test_includes_candidates(self):
        prompt = ClaudeCLIAdapter.build_analysis_prompt(
            {
                "candidates": [
                    {"ticker": "AAPL", "total_score": 0.8, "rsi": 45, "macd_direction": "bullish"}
                ]
            }
        )
        assert "AAPL" in prompt
        assert "Candidates" in prompt

    def test_includes_news(self):
        prompt = ClaudeCLIAdapter.build_analysis_prompt(
            {"news": [{"headline": "Market Rally", "summary": "Stocks are up"}]}
        )
        assert "Market Rally" in prompt

    def test_includes_memory(self):
        prompt = ClaudeCLIAdapter.build_analysis_prompt(
            {
                "memory": [
                    {
                        "ticker": "MSFT",
                        "action": "BUY",
                        "confidence": 0.7,
                        "outcome_assessed": True,
                        "outcome_pnl": 0.05,
                    }
                ]
            }
        )
        assert "MSFT" in prompt
        assert "Past Decisions" in prompt

    def test_empty_package(self):
        prompt = ClaudeCLIAdapter.build_analysis_prompt({})
        assert "No data available" in prompt


class TestReinforcementPrompt:
    def test_includes_error(self):
        prompt = ClaudeCLIAdapter._build_reinforcement_prompt(
            "original", "parse error detail"
        )
        assert "parse error detail" in prompt
        assert "JSON" in prompt
