class TradeAgentError(Exception):
    """Base exception for all TradeAgent errors."""


class ConfigurationError(TradeAgentError):
    """Invalid or missing configuration."""


class PipelineError(TradeAgentError):
    """Pipeline orchestration failure."""


class DataIngestionError(PipelineError):
    """Market data or news fetch failure."""


class LLMError(PipelineError):
    """LLM adapter failure (timeout, parse error, CLI error)."""


class BrokerError(TradeAgentError):
    """Broker adapter failure (order placement, status polling)."""


class RiskValidationError(TradeAgentError):
    """Risk manager rejected a trade."""


class RepositoryError(TradeAgentError):
    """Database query or persistence failure."""


class ValidationError(TradeAgentError):
    """Input validation failure (API layer)."""
