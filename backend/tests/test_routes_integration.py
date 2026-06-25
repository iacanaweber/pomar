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
    client = TestClient(create_app(), base_url="http://testserver")
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


@pytest.fixture
def _stub_cdi(monkeypatch):
    async def fake_cdi(self):
        return 0.1415
    monkeypatch.setattr("app.clients.sgs_bcb.SgsClient.cdi_annual", fake_cdi)


def test_fixed_income_account_and_yield(authed_client, _stub_cdi):
    c = authed_client
    acc = c.post("/api/fixed-income/accounts", json={"name": "CDB X", "kind": "cdb"}).json()
    assert acc["current_balance"] == 0.0 and acc["last_yield_annual"] is None
    aid = acc["id"]
    # saldo inicial e atualização posterior -> rendimento calculado
    c.post(f"/api/fixed-income/accounts/{aid}/entries",
           json={"kind": "balance", "amount": 10_000.0, "entry_date": "2025-01-02"})
    upd = c.post(f"/api/fixed-income/accounts/{aid}/entries",
                 json={"kind": "balance", "amount": 10_135.0, "entry_date": "2025-02-03"}).json()
    assert upd["current_balance"] == 10_135.0
    assert abs(upd["last_yield_gain"] - 135.0) < 1e-6
    assert upd["last_yield_annual"] is not None
    assert upd["pct_of_cdi"] is not None  # CDI veio do stub
    summary = c.get("/api/fixed-income/summary").json()
    assert summary["total_balance"] == 10_135.0
    assert summary["cdi_annual"] == 0.1415


def test_fixed_income_list_and_delete_entry(authed_client, _stub_cdi):
    c = authed_client
    aid = c.post("/api/fixed-income/accounts", json={"name": "Conta X"}).json()["id"]
    c.post(f"/api/fixed-income/accounts/{aid}/entries",
           json={"kind": "deposit", "amount": 10_000.0, "entry_date": "2026-06-01"})
    c.post(f"/api/fixed-income/accounts/{aid}/entries",
           json={"kind": "balance", "amount": 10_120.0, "entry_date": "2026-06-25"})
    items = c.get(f"/api/fixed-income/accounts/{aid}/entries").json()["items"]
    assert len(items) == 2
    # remove o aporte (errado) e confirma que sumiu
    eid = next(i["id"] for i in items if i["kind"] == "deposit")
    assert c.delete(f"/api/fixed-income/accounts/{aid}/entries/{eid}").status_code == 200
    left = c.get(f"/api/fixed-income/accounts/{aid}/entries").json()["items"]
    assert len(left) == 1 and left[0]["kind"] == "balance"


def test_plan_reserve_directs_aporte(authed_client, _stub_cdi, monkeypatch):
    """Com reserve_target, parte do aporte é direcionada à reserva (sem depender de rede)."""
    from app.models.portfolio import Allocations, Portfolio

    async def empty_portfolio(*a, **k):
        return Portfolio(total_value=0.0, as_of="2026-01-01T00:00:00Z", allocations=Allocations())

    async def no_assets(*a, **k):
        return []

    monkeypatch.setattr("app.api.routes_plan.get_enriched_portfolio", empty_portfolio)
    monkeypatch.setattr("app.api.routes_plan.build_universe", no_assets)
    monkeypatch.setattr("app.api.routes_plan.get_sgs", lambda: _StubSgs())

    r = authed_client.post(
        "/api/plan",
        json={"aporte": 1000.0, "reserve_target": 0.3, "reserve_current": 0.0},
    ).json()
    assert r["reserve"] is not None
    # patrimônio resultante = 0 + 0 + 1000; alvo 30% = 300 -> direciona 300, sobra 700 p/ RV
    assert r["reserve"]["directed_now"] == 300.0
    assert r["reserve"]["benchmark_cdi_annual"] == 0.1415


class _StubSgs:
    async def cdi_annual(self):
        return 0.1415


def test_orders_crud(authed_client):
    c = authed_client
    r = c.post("/api/orders", json={"ticker": "bbas3", "shares": 100, "price": 25.0, "fees": 2.0}).json()
    assert r["ticker"] == "BBAS3" and r["shares"] == 100
    lst = c.get("/api/orders").json()
    assert lst["total_invested"] == 100 * 25.0 + 2.0
    assert len(lst["items"]) == 1
    assert c.delete(f"/api/orders/{r['id']}").status_code == 200
    assert c.get("/api/orders").json()["items"] == []


def test_income_goal_with_persisted_target(authed_client, monkeypatch):
    from app.models.portfolio import Allocations, Portfolio

    async def empty_pf(*a, **k):
        return Portfolio(total_value=0.0, as_of="2026-01-01T00:00:00Z", allocations=Allocations())

    monkeypatch.setattr("app.api.routes_income.get_enriched_portfolio", empty_pf)
    c = authed_client
    c.put("/api/preferences", json={"target_monthly_income": 5000.0})
    g = c.get("/api/income/goal").json()
    assert g["target_monthly_income"] == 5000.0
    assert g["gap_monthly"] == 5000.0   # carteira vazia → renda atual 0
    assert g["pct_achieved"] == 0.0
    assert g["required_monthly_contribution"] is not None
