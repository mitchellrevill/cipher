import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from redactor.auth import CurrentUser, get_current_user
from redactor.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_current_user_accepts_dev_bypass(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("DEV_BYPASS", "true")

    app = FastAPI()

    @app.get("/me")
    async def me(current_user: CurrentUser = Depends(get_current_user)):
        return current_user.__dict__

    client = TestClient(app)
    response = client.get("/me", headers={"Authorization": "Bearer dev-token-bypass"})

    assert response.status_code == 200
    assert response.json()["user_id"] == "dev-user-123"


def test_get_current_user_requires_bearer_token():
    app = FastAPI()

    @app.get("/me")
    async def me(current_user: CurrentUser = Depends(get_current_user)):
        return current_user.__dict__

    client = TestClient(app)
    response = client.get("/me")

    assert response.status_code == 401
