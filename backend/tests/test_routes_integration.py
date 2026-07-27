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
    assert p["min_ticket"] == 100.0
    r = c.put("/api/preferences", json={"min_ticket": 250.0, "lot_mode": "integral"})
    assert r.status_code == 200
    p2 = c.get("/api/preferences").json()
    assert p2["min_ticket"] == 250.0 and p2["lot_mode"] == "integral"


def test_class_targets_must_sum_to_100(authed_client):
    c = authed_client
    bad = c.put("/api/preferences", json={"class_targets": {"FII": {"A11": 0.5, "B11": 0.3}}})
    assert bad.status_code == 422
    ok = c.put("/api/preferences", json={"class_targets": {"FII": {"A11": 0.7, "B11": 0.3}}})
    assert ok.status_code == 200
    assert c.get("/api/preferences").json()["class_targets"] == {"FII": {"A11": 0.7, "B11": 0.3}}


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


def _stub_plan_market(monkeypatch, assets=None, portfolio=None):
    """Isola o plano da rede: carteira e dados de mercado vêm de stubs."""
    from app.models.portfolio import Allocations, Portfolio

    pf = portfolio or Portfolio(
        total_value=0.0, as_of="2026-01-01T00:00:00Z", allocations=Allocations()
    )

    async def _portfolio(*a, **k):
        return pf

    async def _universe(*a, **k):
        return list(assets or [])

    monkeypatch.setattr("app.api.routes_plan.get_enriched_portfolio", _portfolio)
    monkeypatch.setattr("app.api.routes_plan.build_universe", _universe)
    monkeypatch.setattr("app.api.routes_plan.get_sgs", lambda: _StubSgs())


def _asset(ticker, asset_class, price, dividends=None):
    from app.models.market import Asset, Fundamentals

    return Asset(
        ticker=ticker, asset_class=asset_class, price=price,
        fundamentals=Fundamentals(pvp=1.0, pl=8.0, dividend_yield=0.08),
        dividends_by_year=dividends or {"2022": 2.0, "2023": 2.0, "2024": 2.0},
    )


def test_plan_reserve_directs_aporte(authed_client, _stub_cdi, monkeypatch):
    """Com reserve_target, parte do aporte é direcionada à reserva (sem depender de rede)."""
    c = authed_client
    c.put("/api/preferences", json={"class_targets": {"STOCK": {"AAA3": 1.0}}})
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])

    r = c.post(
        "/api/plan",
        json={"aporte": 1000.0, "classes": ["STOCK"], "reserve_target": 0.3,
              "reserve_current": 0.0, "min_ticket": 10.0},
    ).json()
    assert r["reserve"] is not None
    # patrimônio resultante = 0 + 0 + 1000; alvo 30% = 300 -> direciona 300, sobra 700 p/ RV
    assert r["reserve"]["directed_now"] == 300.0
    assert r["reserve"]["benchmark_cdi_annual"] == 0.1415
    bought = next(x for x in r["ranking"] if x["ticker"] == "AAA3")
    assert bought["suggested"]["invested_exact"] == 700.0
    assert r["plan_id"] is not None  # o save é best-effort: erro de contrato seria silencioso


def test_plan_skips_class_without_composition(authed_client, monkeypatch):
    c = authed_client
    c.put("/api/preferences", json={"class_targets": {"STOCK": {"AAA3": 1.0}}})
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])

    r = c.post(
        "/api/plan",
        json={"aporte": 500.0, "classes": ["STOCK", "FII"], "min_ticket": 10.0},
    ).json()
    assert r["classes_applied"] == ["STOCK"]
    assert r["classes_skipped"] == ["FII"]
    assert any("sem composição" in w for w in r["warnings"])
    assert {x["ticker"] for x in r["ranking"]} == {"AAA3"}


def test_plan_without_any_composition_is_422(authed_client, monkeypatch):
    _stub_plan_market(monkeypatch)
    r = authed_client.post("/api/plan", json={"aporte": 500.0})
    assert r.status_code == 422
    assert "carteira alvo" in r.json()["detail"].lower()


def test_plan_rejects_invalid_or_empty_classes(authed_client, monkeypatch):
    c = authed_client
    c.put("/api/preferences", json={"class_targets": {"STOCK": {"AAA3": 1.0}}})
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])
    assert c.post("/api/plan", json={"aporte": 100.0, "classes": ["XPTO"]}).status_code == 422
    assert c.post("/api/plan", json={"aporte": 100.0, "classes": []}).status_code == 422


def test_plan_ignores_retired_fields_from_old_clients(authed_client, monkeypatch):
    """Front antigo (ou aba aberta há dias) manda strategy/focus/max_assets: são ignorados,
    não quebram o aporte."""
    c = authed_client
    c.put("/api/preferences", json={"class_targets": {"STOCK": {"AAA3": 1.0}}})
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])
    r = c.post("/api/plan", json={
        "aporte": 100.0, "strategy": "barsi", "focus": "FII", "max_assets": 3,
        "max_weight_per_asset": 0.2, "weights": {"valuation": 1.0}, "min_ticket": 10.0,
    })
    assert r.status_code == 200


def test_plan_marks_discount_even_without_purchase(authed_client, monkeypatch):
    """Ativo no peso-alvo (compra 0) continua no ranking marcado como abaixo do teto —
    é o gatilho para o usuário antecipar por conta própria."""
    from app.models.portfolio import Allocations, Portfolio, Position

    c = authed_client
    c.put("/api/preferences", json={"class_targets": {"STOCK": {"AAA3": 0.5, "BBB3": 0.5}}})
    pf = Portfolio(
        total_value=2000.0, as_of="2026-01-01T00:00:00Z",
        positions=[
            Position(ticker="AAA3", asset_class="STOCK", value=1000.0, weight=0.5),
            Position(ticker="BBB3", asset_class="STOCK", value=1000.0, weight=0.5),
        ],
        allocations=Allocations(by_class={"STOCK": 1.0}),
    )
    # AAA3 a R$ 10 com dividendo médio 2,0 => teto 33,33 (bem abaixo do teto)
    _stub_plan_market(
        monkeypatch,
        [_asset("AAA3", "STOCK", 10.0), _asset("BBB3", "STOCK", 100.0)],
        portfolio=pf,
    )
    r = c.post(
        "/api/plan",
        json={"aporte": 100.0, "classes": ["STOCK"], "min_ticket": 10.0, "targets": {"STOCK": 1.0}},
    ).json()
    aaa = next(x for x in r["ranking"] if x["ticker"] == "AAA3")
    bbb = next(x for x in r["ranking"] if x["ticker"] == "BBB3")
    assert aaa["bazin_below_ceiling"] is True
    assert bbb["bazin_below_ceiling"] is False
    assert bbb["suggested"] is None
    assert any("sem compra sugerida" in x for x in bbb["reasons"])
    # a barra da cesta chega pronta na UI
    assert aaa["basket_target_pct"] == 0.5 and aaa["basket_current_pct"] == 0.5


def test_plan_latest_reads_a_plan_saved_by_the_old_format(authed_client):
    """Planos gravados antes da v6 (com score, métricas, pesos e foco) precisam continuar
    abrindo — o usuário não pode perder o último plano numa atualização."""
    import asyncio

    from app.deps import get_db
    from app.repositories import plans_repo

    old = {
        "aporte": 1000.0, "currency": "BRL", "as_of": "2026-05-01T00:00:00Z",
        "weights": {"valuation": 0.3, "dividend": 0.35, "rebalance": 0.2, "sector": 0.15},
        "focus": "BALANCE", "targets_by_class": {"STOCK": 1.0}, "current_by_class": {},
        "ranking": [{
            "ticker": "BBAS3", "name": "Banco do Brasil", "asset_class": "STOCK",
            "rank": 1, "composite_score": 0.82, "composite_base": 0.9, "quality_factor": 0.91,
            "data_completeness": "7/8", "risk_level": "verde", "red_flags": [],
            "metrics": [{"key": "pvp", "label": "P/VP", "raw_value": 0.8, "weight": 0.1,
                         "source": "Fundamentus", "available": True}],
            "bazin_ceiling_price": 33.33, "bazin_below_ceiling": True, "bazin_margin": 0.4,
            "suggested": {"target_amount": 500.0, "price": 25.0, "shares": 20,
                          "invested_exact": 500.0, "lot_size": 1},
        }],
        "unallocated": 500.0, "warnings": [],
    }
    asyncio.run(plans_repo.save(get_db(), {"aporte": 1000.0}, old))
    r = authed_client.get("/api/plan/latest")
    assert r.status_code == 200
    body = r.json()
    item = body["ranking"][0]
    assert item["ticker"] == "BBAS3"
    assert item["bazin_ceiling_price"] == 33.33  # o selo de teto sobrevive
    assert item["suggested"]["shares"] == 20
    assert item["basket_target_pct"] is None  # campo novo, ausente no plano antigo


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


def test_asset_detail_returns_factual_analysis(authed_client, monkeypatch):
    """/asset devolve a leitura factual (teto, consistência, flags) — sem nota nem ranking."""
    async def _assets(*a, **k):
        return [_asset("BBAS3", "STOCK", 20.0)]

    monkeypatch.setattr("app.services.market_data.build_assets", _assets)
    body = authed_client.get("/api/asset/BBAS3").json()
    assert body["asset"]["ticker"] == "BBAS3"
    an = body["analysis"]
    assert an["bazin_ceiling_price"] == 33.33 and an["bazin_below_ceiling"] is True
    assert an["dividend_consistency"] == 1.0
    assert an["risk_level"] in ("verde", "amarelo", "vermelho")
    assert "composite_score" not in an and "metrics" not in an
