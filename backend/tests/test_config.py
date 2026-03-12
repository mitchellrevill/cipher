# tests/test_config.py
import pytest
from redactor.config import Settings, get_settings

@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

def test_enable_pii_service_defaults_true():
    s = Settings(_env_file=None)
    assert s.enable_pii_service is True

def test_enable_pii_service_can_be_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_PII_SERVICE", "false")
    s = Settings(_env_file=None)
    assert s.enable_pii_service is False
