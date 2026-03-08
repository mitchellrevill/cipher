# tests/test_config.py
from redactor.config import Settings

def test_enable_pii_service_defaults_true():
    s = Settings()
    assert s.enable_pii_service is True

def test_enable_pii_service_can_be_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_PII_SERVICE", "false")
    s = Settings()
    assert s.enable_pii_service is False
