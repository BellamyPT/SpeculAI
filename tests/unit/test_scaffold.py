"""Smoke tests to verify project scaffolding works correctly."""

from tradeagent.config import Settings
from tradeagent.core.exceptions import TradeAgentError, PipelineError
from tradeagent.core.types import Action, Side, TradeStatus, PipelineStatus, ContextType


def test_settings_defaults():
    s = Settings()
    assert s.portfolio.max_positions == 20
    assert s.portfolio.base_currency == "EUR"
    assert s.screening.weights.rsi == 0.25
    assert s.technical_analysis.rsi_period == 14
    assert s.pipeline.schedule_hour == 7
    assert s.llm.provider == "claude_cli"
    assert len(s.benchmarks) == 3


def test_settings_from_yaml(tmp_path):
    yaml_content = """
portfolio:
  max_positions: 10
  initial_capital: 100000.0
"""
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content)
    s = Settings.from_yaml(yaml_path=yaml_file)
    assert s.portfolio.max_positions == 10
    assert s.portfolio.initial_capital == 100000.0
    # Defaults still hold for unset fields
    assert s.portfolio.base_currency == "EUR"


def test_settings_from_yaml_missing_file(tmp_path):
    s = Settings.from_yaml(yaml_path=tmp_path / "nonexistent.yaml")
    assert s.portfolio.max_positions == 20


def test_enums():
    assert Action.BUY == "BUY"
    assert Side.SELL == "SELL"
    assert TradeStatus.PENDING == "PENDING"
    assert PipelineStatus.SUCCESS == "SUCCESS"
    assert ContextType.NEWS == "news"


def test_exception_hierarchy():
    assert issubclass(PipelineError, TradeAgentError)
    assert issubclass(TradeAgentError, Exception)
