from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class PortfolioConfig(BaseModel):
    max_positions: int = 20
    max_position_pct: float = 5.0
    min_trade_value: float = 100.0
    base_currency: str = "EUR"
    initial_capital: float = 50000.0


class ScreeningWeights(BaseModel):
    rsi: float = 0.25
    macd: float = 0.20
    bollinger: float = 0.15
    sma_cross: float = 0.15
    volume_anomaly: float = 0.10
    pe_undervaluation: float = 0.15


class ScreeningThresholds(BaseModel):
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    volume_anomaly_multiplier: float = 1.5
    bollinger_proximity_pct: float = 5.0


class ScreeningConfig(BaseModel):
    max_candidates: int = 50
    min_market_cap: int = 500_000_000
    weights: ScreeningWeights = ScreeningWeights()
    thresholds: ScreeningThresholds = ScreeningThresholds()


class TechnicalAnalysisConfig(BaseModel):
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bollinger_period: int = 20
    bollinger_std: int = 2
    sma_short: int = 50
    sma_long: int = 200
    ema_short: int = 12
    ema_long: int = 26
    volume_sma_period: int = 20


class PipelineConfig(BaseModel):
    schedule_hour: int = 7
    schedule_minute: int = 0
    max_llm_retries: int = 3
    llm_timeout_seconds: int = 120
    broker_retry_delay_minutes: int = 30
    broker_max_retries: int = 2


class LLMConfig(BaseModel):
    provider: str = "claude_cli"
    temperature: float = 0.3
    system_prompt_path: str = "src/tradeagent/adapters/llm/prompts/system_prompt.md"
    max_output_tokens: int = 3000


class NewsConfig(BaseModel):
    provider: str = "perplexity"
    queries_per_run: int = 8
    sectors: list[str] = [
        "technology",
        "semiconductors",
        "artificial intelligence",
        "energy",
        "healthcare",
        "financials",
        "consumer discretionary",
        "cybersecurity",
    ]


class MemoryConfig(BaseModel):
    max_items_per_candidate: int = 10
    exact_ticker_max: int = 10
    sector_max: int = 5
    outcome_lookback_days: int = 7


class BenchmarkItem(BaseModel):
    symbol: str
    name: str


_DEFAULT_BENCHMARKS = [
    BenchmarkItem(symbol="^GSPC", name="S&P 500"),
    BenchmarkItem(symbol="IWDA.AS", name="iShares Core MSCI World"),
    BenchmarkItem(symbol="VWCE.DE", name="Vanguard FTSE All-World"),
]


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load YAML config file if it exists, return empty dict otherwise."""
    if path.is_file():
        with open(path) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Environment variables
    database_url: str = "postgresql://tradeagent:tradeagent_dev@localhost:5432/tradeagent"
    t212_api_key: str = ""
    t212_api_secret: str = ""
    t212_base_url: str = "https://demo.trading212.com/api/v0"
    perplexity_api_key: str = ""
    perplexity_model: str = "sonar"
    claude_cli_path: str = "claude"
    claude_cli_timeout: int = 120
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:5173"

    # YAML-loaded config sections
    portfolio: PortfolioConfig = PortfolioConfig()
    screening: ScreeningConfig = ScreeningConfig()
    technical_analysis: TechnicalAnalysisConfig = TechnicalAnalysisConfig()
    pipeline: PipelineConfig = PipelineConfig()
    llm: LLMConfig = LLMConfig()
    news: NewsConfig = NewsConfig()
    memory: MemoryConfig = MemoryConfig()
    benchmarks: list[BenchmarkItem] = _DEFAULT_BENCHMARKS

    @classmethod
    def from_yaml(
        cls, yaml_path: str | Path = "config/config.yaml", **overrides: Any
    ) -> Settings:
        """Create Settings by merging YAML config with env vars.

        YAML values act as defaults; environment variables take precedence
        via Pydantic Settings' normal resolution order.
        """
        yaml_data = _load_yaml_config(Path(yaml_path))
        merged = {**yaml_data, **overrides}
        return cls(**merged)
