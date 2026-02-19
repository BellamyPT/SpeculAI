import pytest

from tradeagent.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Provide default Settings instance for tests."""
    return Settings()
