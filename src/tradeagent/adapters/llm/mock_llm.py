"""Mock LLM adapter — returns deterministic responses for testing/backtesting."""

from __future__ import annotations

import time
from typing import Any

from tradeagent.adapters.base import LLMAdapter, LLMResponse


class MockLLMAdapter(LLMAdapter):
    """LLM adapter that returns pre-set or default deterministic responses."""

    def __init__(self, default_response: dict | None = None) -> None:
        self._response = default_response

    def set_response(self, response: dict) -> None:
        """Set the response that will be returned by the next analyze() call."""
        self._response = response

    async def analyze(
        self,
        analysis_package: dict[str, Any],
        *,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Return the pre-set response or a default based on top candidates."""
        start = time.monotonic()

        if self._response is not None:
            parsed = self._response
        else:
            parsed = self._build_default_response(analysis_package)

        elapsed = time.monotonic() - start
        return LLMResponse(
            raw_text=str(parsed),
            parsed=parsed,
            token_count=100,
            response_time_seconds=elapsed,
            parse_success=True,
        )

    @staticmethod
    def _build_default_response(analysis_package: dict) -> dict:
        """Build a reasonable default: BUY top candidate, HOLD the rest."""
        candidates = analysis_package.get("candidates", [])
        recommendations = []

        for i, candidate in enumerate(candidates[:3]):
            action = "BUY" if i == 0 else "HOLD"
            recommendations.append({
                "ticker": candidate.get("ticker", ""),
                "action": action,
                "confidence": 0.7 if action == "BUY" else 0.3,
                "reasoning": f"Mock analysis for {candidate.get('ticker', '')}",
                "suggested_allocation_pct": 3.0 if action == "BUY" else 0.0,
            })

        return {
            "recommendations": recommendations,
            "market_outlook": "neutral",
            "summary": "Mock LLM analysis",
        }
