Generate a decision report summarizing today's pipeline analysis.

## Report Requirements

1. **Market Overview**: Brief assessment of current market conditions based on the news provided.
2. **Candidate Analysis**: For each analyzed stock, summarize key technical and fundamental signals.
3. **Trade Decisions**: List each BUY/SELL/HOLD decision with confidence and reasoning.
4. **Risk Assessment**: Identify any portfolio concentration risks or market risks.
5. **Memory Insights**: Reference any relevant past decisions and their outcomes.

## Response Format

Respond with a single valid JSON object:

```json
{
  "report": {
    "market_overview": "...",
    "candidate_analyses": [
      {
        "ticker": "...",
        "summary": "...",
        "key_signals": ["..."],
        "decision": "BUY/SELL/HOLD",
        "confidence": 0.0
      }
    ],
    "risk_assessment": "...",
    "memory_insights": "..."
  }
}
```
