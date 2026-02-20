"""Claude CLI adapter — invokes the Claude CLI subprocess for LLM analysis."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from tradeagent.adapters.base import LLMAdapter, LLMResponse
from tradeagent.core.exceptions import LLMError
from tradeagent.core.logging import get_logger

log = get_logger(__name__)


class ClaudeCLIAdapter(LLMAdapter):
    """LLM adapter that shells out to the Claude CLI binary.

    Security: prompt content and response content are never logged
    (per project rules). Only token count, response time, and
    success/failure are logged.
    """

    def __init__(
        self,
        cli_path: str = "claude",
        timeout_seconds: int = 120,
        max_retries: int = 3,
        system_prompt_path: str | None = None,
    ) -> None:
        self._cli_path = cli_path
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._system_prompt: str | None = None
        if system_prompt_path and Path(system_prompt_path).is_file():
            self._system_prompt = Path(system_prompt_path).read_text()

    # ── Public API ───────────────────────────────────────────────────

    async def analyze(
        self,
        analysis_package: dict[str, Any],
        *,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Invoke the CLI, parse JSON response, retry on parse failure."""
        prompt = self.build_analysis_prompt(analysis_package)
        if system_prompt or self._system_prompt:
            prompt = (system_prompt or self._system_prompt or "") + "\n\n" + prompt

        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                raw_text, elapsed = await self._invoke_cli(prompt)
                parsed = self._extract_json(raw_text)

                log.info(
                    "llm_analysis_complete",
                    attempt=attempt + 1,
                    response_time=round(elapsed, 2),
                    parse_success=True,
                )
                return LLMResponse(
                    raw_text=raw_text,
                    parsed=parsed,
                    token_count=len(raw_text.split()),
                    response_time_seconds=elapsed,
                    parse_success=True,
                )
            except ValueError as exc:
                last_error = exc
                log.warning(
                    "llm_parse_failed",
                    attempt=attempt + 1,
                    error=str(exc),
                )
                # Build a reinforcement prompt for retry
                prompt = self._build_reinforcement_prompt(prompt, str(exc))
            except LLMError:
                raise
            except Exception as exc:
                raise LLMError(f"LLM analysis failed: {exc}") from exc

        raise LLMError(
            f"Failed to parse LLM response after {self._max_retries} attempts: {last_error}"
        )

    # ── CLI invocation ───────────────────────────────────────────────

    async def _invoke_cli(self, prompt: str) -> tuple[str, float]:
        """Run the Claude CLI as a subprocess and return (stdout, elapsed_seconds).

        Raises LLMError on failure.
        """
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                self._cli_path,
                "--print",
                "--output-format", "json",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=self._timeout,
            )
        except FileNotFoundError:
            raise LLMError(f"Claude CLI not found at: {self._cli_path}")
        except asyncio.TimeoutError:
            raise LLMError(f"Claude CLI timed out after {self._timeout}s")

        elapsed = time.monotonic() - start

        if proc.returncode != 0:
            raise LLMError(
                f"Claude CLI exited with code {proc.returncode}"
            )

        output = stdout.decode().strip()
        if not output:
            raise LLMError("Claude CLI returned empty output")

        log.info(
            "cli_invocation_complete",
            response_time=round(elapsed, 2),
            exit_code=proc.returncode,
        )
        return output, elapsed

    # ── JSON extraction ──────────────────────────────────────────────

    @staticmethod
    def _extract_json(raw_text: str) -> dict:
        """Extract the first JSON object from raw text.

        Finds the first ``{`` and last ``}`` and attempts ``json.loads``.
        Raises ValueError if no valid JSON is found.
        """
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found in response")

        json_str = raw_text[start : end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

    # ── Prompt building ──────────────────────────────────────────────

    @staticmethod
    def build_analysis_prompt(analysis_package: dict[str, Any]) -> str:
        """Format the analysis package into a readable prompt for the LLM."""
        sections: list[str] = []

        # Portfolio state
        portfolio = analysis_package.get("portfolio_state", {})
        if portfolio:
            sections.append(
                "## Portfolio State\n"
                f"Total value: {portfolio.get('total_value', 'N/A')}\n"
                f"Cash available: {portfolio.get('cash_available', 'N/A')}\n"
                f"Open positions: {portfolio.get('num_positions', 'N/A')}"
            )

        # Candidates
        candidates = analysis_package.get("candidates", [])
        if candidates:
            lines = ["## Candidates"]
            for c in candidates:
                lines.append(
                    f"- **{c.get('ticker', '?')}** "
                    f"(score: {c.get('total_score', 'N/A')}, "
                    f"RSI: {c.get('rsi', 'N/A')}, "
                    f"MACD: {c.get('macd_direction', 'N/A')})"
                )
            sections.append("\n".join(lines))

        # News
        news = analysis_package.get("news", [])
        if news:
            lines = ["## Recent News"]
            for n in news:
                lines.append(f"- {n.get('headline', 'N/A')}: {n.get('summary', '')[:200]}")
            sections.append("\n".join(lines))

        # Memory
        memory = analysis_package.get("memory", [])
        if memory:
            lines = ["## Past Decisions (Memory)"]
            for m in memory:
                outcome = (
                    f"P&L: {m.get('outcome_pnl', 'N/A')}"
                    if m.get("outcome_assessed")
                    else "pending"
                )
                lines.append(
                    f"- {m.get('ticker', '?')} {m.get('action', '?')} "
                    f"(conf: {m.get('confidence', 'N/A')}, {outcome})"
                )
            sections.append("\n".join(lines))

        prompt = "\n\n".join(sections) if sections else "No data available."
        prompt += (
            "\n\n## Instructions\n"
            "Analyze the candidates and return a JSON object with your trade "
            "recommendations. For each recommendation include: ticker, action "
            "(BUY/SELL/HOLD), confidence (0-1), reasoning, and "
            "suggested_allocation_pct."
        )
        return prompt

    @staticmethod
    def _build_reinforcement_prompt(original: str, parse_error: str) -> str:
        """Build a retry prompt emphasizing JSON format after a parse failure."""
        return (
            f"{original}\n\n"
            f"IMPORTANT: Your previous response could not be parsed as JSON. "
            f"Error: {parse_error}\n"
            f"Please respond with ONLY a valid JSON object. No markdown, no "
            f"code fences, no explanation — just the raw JSON."
        )
