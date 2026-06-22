"""Integração HTTP: preferências e watchlist atrás da autenticação, com DB temporário."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.deps import get_db
from app.main import create_app


@pytest.fixture
def authed_client(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_PASSWORD", "pw")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    get_settings.cache_clear()
    get_db.cache_clear()
    client = TestClient(create_app(), base_url="https://testserver")
    client.post("/api/login", json={"password": "pw"})
    yield client
    get_settings.cache_clear()
    get_db.cache_clear()


def test_preferences_requires_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_PASSWORD", "pw")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    get_settings.cache_clear()
    get_db.cache_clear()
    c = TestClient(create_app(), base_url="https://testserver")
    assert c.get("/api/preferences").status_code == 401  # sem login
    get_settings.cache_clear()
    get_db.cache_clear()


def test_preferences_get_put_roundtrip(authed_client):
    c = authed_client
    p = c.get("/api/preferences").json()
    assert p["strategy"] == "equilibrado"
    r = c.put("/api/preferences", json={"strategy": "graham", "max_assets": 7})
    assert r.status_code == 200
    p2 = c.get("/api/preferences").json()
    assert p2["strategy"] == "graham" and p2["max_assets"] == 7


def test_watchlist_seeded_on_first_get(authed_client):
    items = authed_client.get("/api/watchlist").json()["items"]
    assert len(items) > 0
    tickers = {i["ticker"] for i in items}
    assert "BBAS3" in tickers  # da watchlist curada (seed)
