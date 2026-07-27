"""Testes de autenticação por senha única e de validação de configuração."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def client_with_password(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "segredo123")
    monkeypatch.setenv("DEBUG", "false")
    get_settings.cache_clear()
    app = create_app()
    # base_url HTTP: cobre o cenário real de deploy LAN (sem TLS). Como COOKIE_SECURE é
    # False por padrão, o cookie de sessão é armazenado e reenviado sobre HTTP — se fosse
    # Secure, o login "não avançaria" (bug corrigido). Sem `with` => não dispara o warmup.
    yield TestClient(app, base_url="http://testserver")
    get_settings.cache_clear()


def test_health_is_open(client_with_password):
    assert client_with_password.get("/api/health").status_code in (200, 502, 503)
    # /health nunca deve ser 401 (rota aberta)
    assert client_with_password.get("/api/health").status_code != 401


def test_protected_route_requires_auth(client_with_password):
    assert client_with_password.get("/api/glossary").status_code == 401


def test_login_flow(client_with_password):
    c = client_with_password
    assert c.post("/api/login", json={"password": "errada"}).status_code == 401
    r = c.post("/api/login", json={"password": "segredo123"})
    assert r.status_code == 200
    # cookie de sessão setado => rota protegida agora responde
    assert c.get("/api/glossary").status_code == 200
    # logout invalida o acesso
    c.post("/api/logout")
    assert c.get("/api/glossary").status_code == 401


def test_auth_status(client_with_password):
    c = client_with_password
    assert c.get("/api/auth/status").json() == {"auth_required": True, "authenticated": False}
    c.post("/api/login", json={"password": "segredo123"})
    assert c.get("/api/auth/status").json()["authenticated"] is True


def test_docs_hidden_without_debug(client_with_password):
    assert client_with_password.get("/openapi.json").status_code == 404
    assert client_with_password.get("/docs").status_code == 404


def test_without_password_protected_routes_return_503(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "")
    get_settings.cache_clear()
    app = create_app()
    c = TestClient(app)
    assert c.get("/api/glossary").status_code == 503
    assert c.get("/api/health").status_code != 503  # health continua aberto
    get_settings.cache_clear()


def test_debug_enables_docs(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "x")
    monkeypatch.setenv("DEBUG", "true")
    get_settings.cache_clear()
    app = create_app()
    c = TestClient(app)
    assert c.get("/openapi.json").status_code == 200
    get_settings.cache_clear()


# --- validação de configuração ---

def test_targets_must_sum_to_one():
    with pytest.raises(ValueError):
        Settings(default_targets={"STOCK": 0.5, "FII": 0.2})


def test_targets_reject_unknown_class():
    with pytest.raises(ValueError):
        Settings(default_targets={"STOCK": 0.5, "CRYPTO": 0.5})


def test_brapi_plan_validation():
    with pytest.raises(ValueError):
        Settings(brapi_plan="enterprise")
    assert Settings(brapi_plan="PRO").brapi_plan == "pro"
