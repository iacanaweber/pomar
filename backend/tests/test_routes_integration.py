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
    acc = c.post(
        "/api/fixed-income/accounts",
        json={"name": "CDB X", "kind": "cdb", "liquidity": "immediate"},
    ).json()
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
    aid = c.post(
        "/api/fixed-income/accounts", json={"name": "Conta X", "liquidity": "immediate"}
    ).json()["id"]
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


def _stub_plan_market(monkeypatch, assets=None, portfolio=None, ipca_factor=None):
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
    monkeypatch.setattr("app.api.routes_plan.get_sgs", lambda: _StubSgs(ipca_factor))


def _asset(ticker, asset_class, price, dividends=None):
    from app.models.market import Asset, Fundamentals

    return Asset(
        ticker=ticker, asset_class=asset_class, price=price,
        fundamentals=Fundamentals(pvp=1.0, pl=8.0, dividend_yield=0.08),
        dividends_by_year=dividends or {"2022": 2.0, "2023": 2.0, "2024": 2.0},
    )


def test_plan_floor_deficit_comes_before_any_purchase(authed_client, _stub_cdi, monkeypatch):
    """O déficit do piso tem prioridade absoluta: o que sobra é que compra renda variável."""
    c = authed_client
    c.put("/api/preferences", json={
        "class_targets": {"STOCK": {"AAA3": 1.0}},
        "reserve_floor_amount": 30_000.0,
    })
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])

    r = c.post(
        "/api/plan",
        json={"aporte": 1000.0, "classes": ["STOCK"], "reserve_current": 29_700.0,
              "min_ticket": 10.0},
    ).json()
    assert r["reserve"] is not None
    assert r["reserve"]["target_amount"] == 30_000.0
    assert r["reserve"]["current_amount"] == 29_700.0
    assert r["reserve"]["gap"] == 300.0
    assert r["reserve"]["directed_now"] == 300.0
    assert r["reserve"]["benchmark_cdi_annual"] == 0.1415
    bought = next(x for x in r["ranking"] if x["ticker"] == "AAA3")
    assert bought["suggested"]["invested_exact"] == 700.0
    assert r["plan_id"] is not None  # o save é best-effort: erro de contrato seria silencioso


def test_plan_without_floor_has_no_reserve_card(authed_client, monkeypatch):
    """Default preserva o comportamento: sem piso configurado, nada é desviado."""
    c = authed_client
    c.put("/api/preferences", json={"class_targets": {"STOCK": {"AAA3": 1.0}}})
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])
    r = c.post("/api/plan", json={"aporte": 1000.0, "classes": ["STOCK"], "min_ticket": 10.0}).json()
    assert r["reserve"] is None
    assert next(x for x in r["ranking"] if x["ticker"] == "AAA3")["suggested"]["invested_exact"] == 1000.0


def test_plan_floor_only_counts_immediately_liquid_money(authed_client, _stub_cdi, monkeypatch):
    """A LCI travada soma no patrimônio, mas não cobre o piso: dizer que a reserva está
    cumprida enquanto o dinheiro está preso é a falha que a reserva existe para evitar."""
    c = authed_client
    lci = _conta(c, "LCI 2 anos", counts_in_portfolio=True, liquidity="locked").json()
    selic = _conta(c, "Tesouro Selic", counts_in_portfolio=True).json()
    _saldo(c, lci["id"], 25_000.0)
    _saldo(c, selic["id"], 5_000.0)

    c.put("/api/preferences", json={
        "class_targets": {"STOCK": {"AAA3": 1.0}},
        "reserve_floor_amount": 10_000.0,
    })
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])
    r = c.post("/api/plan", json={"aporte": 1000.0, "classes": ["STOCK"], "min_ticket": 10.0}).json()
    # reserva líquida = 5.000 (só a Selic), então ainda faltam 5.000 para o piso
    assert r["reserve"]["current_amount"] == 5_000.0
    assert r["reserve"]["gap"] == 5_000.0
    assert r["reserve"]["directed_now"] == 1000.0  # o aporte inteiro vai para o piso
    assert not any(x["suggested"] for x in r["ranking"])


def test_plan_floor_falls_back_to_nominal_when_ipca_fails(authed_client, _stub_cdi, monkeypatch):
    """Falha do SGS nunca quebra a tela: vale o nominal, e o plano diz que a correção
    está indisponível."""
    c = authed_client
    c.put("/api/preferences", json={
        "class_targets": {"STOCK": {"AAA3": 1.0}},
        "reserve_floor_amount": 30_000.0,
        "reserve_floor_date": "2026-01-01",
        "reserve_floor_index": "ipca",
    })

    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)], ipca_factor=None)
    r = c.post(
        "/api/plan",
        json={"aporte": 100.0, "classes": ["STOCK"], "reserve_current": 30_000.0, "min_ticket": 10.0},
    ).json()
    assert r["reserve"]["target_amount"] == 30_000.0  # o nominal
    assert r["reserve"]["floor_index"] == "ipca"
    assert r["reserve"]["floor_index_available"] is False
    assert any("IPCA" in w for w in r["warnings"])


def test_plan_floor_is_corrected_by_ipca(authed_client, _stub_cdi, monkeypatch):
    c = authed_client
    c.put("/api/preferences", json={
        "class_targets": {"STOCK": {"AAA3": 1.0}},
        "reserve_floor_amount": 30_000.0,
        "reserve_floor_date": "2026-01-01",
        "reserve_floor_index": "ipca",
    })

    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)], ipca_factor=1.0325)
    r = c.post(
        "/api/plan",
        json={"aporte": 100.0, "classes": ["STOCK"], "reserve_current": 30_000.0, "min_ticket": 10.0},
    ).json()
    assert r["reserve"]["floor_nominal"] == 30_000.0
    assert r["reserve"]["target_amount"] == 30_975.0
    assert r["reserve"]["gap"] == 975.0
    assert r["reserve"]["directed_now"] == 100.0  # o aporte residual que a correção provoca


def test_reserve_target_retirement_seeds_renda_fixa_weight(authed_client):
    """O mecanismo aposentado vira PESO da classe, não piso: converter uma fração do
    patrimônio em um valor em R$ não teria significado."""
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.5, "FII": 0.3, "ETF": 0.15, "BDR": 0.05},
        "reserve_target": 0.2,
    })
    p = c.get("/api/preferences").json()
    assert p["targets"]["RENDA_FIXA"] == 0.2
    assert p["targets"]["STOCK"] == 0.4  # 0.5 × (1 − 0.2)
    assert sum(p["targets"].values()) == pytest.approx(1.0)
    assert p["reserve_floor_amount"] == 0.0  # o piso nasce zerado e é pedido uma vez
    # idempotente: a segunda leitura não renormaliza de novo
    assert c.get("/api/preferences").json()["targets"]["STOCK"] == 0.4


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
    def __init__(self, ipca_factor=None):
        self._ipca = ipca_factor

    async def cdi_annual(self):
        return 0.1415

    async def ipca_factor_since(self, start):
        """None simula o SGS fora do ar — o piso tem de cair no nominal, não estourar."""
        return self._ipca


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


def test_asset_starved_by_class_says_so(authed_client, monkeypatch):
    """Ativo muito abaixo do peso na cesta, mas de uma classe já no alvo, não pode dizer
    'no alvo' — a explicação tem que apontar a classe, senão contradiz a própria barra."""
    from app.models.portfolio import Allocations, Portfolio, Position

    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.5, "FII": 0.5},
        "class_targets": {"STOCK": {"AAA3": 0.5, "BBB3": 0.5}, "FII": {"CCC11": 1.0}},
    })
    # STOCK vale 1000 (só AAA3) e FII vale 0 => todo o aporte vai para FII, mesmo com
    # BBB3 a 50 p.p. do alvo dentro da cesta de ações
    pf = Portfolio(
        total_value=1000.0, as_of="2026-01-01T00:00:00Z",
        positions=[Position(ticker="AAA3", asset_class="STOCK", value=1000.0, weight=1.0)],
        allocations=Allocations(by_class={"STOCK": 1.0}),
    )
    _stub_plan_market(
        monkeypatch,
        [_asset("AAA3", "STOCK", 10.0), _asset("BBB3", "STOCK", 10.0), _asset("CCC11", "FII", 10.0)],
        portfolio=pf,
    )
    r = c.post("/api/plan", json={"aporte": 500.0, "min_ticket": 10.0}).json()
    bbb = next(x for x in r["ranking"] if x["ticker"] == "BBB3")
    assert bbb["suggested"] is None
    assert any("abaixo do alvo na cesta" in x for x in bbb["reasons"])
    assert any("já está no peso-alvo da carteira" in x for x in bbb["reasons"])
    assert not any("No alvo ou acima" in x for x in bbb["reasons"])
    ccc = next(x for x in r["ranking"] if x["ticker"] == "CCC11")
    assert ccc["suggested"]["invested_exact"] == 500.0


def test_plan_uses_saved_class_targets(authed_client, monkeypatch):
    """As metas por classe salvas nas preferências mandam no orçamento do plano.

    Regressão: o plano lia `req.targets or settings.default_targets` e ignorava as
    preferências — como a UI parou de enviar `targets`, todo aporte era dividido pelo
    default hardcoded assim que a meta salva divergia dele.
    """
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.5, "FII": 0.3, "ETF": 0.2, "BDR": 0.0},
        "class_targets": {"STOCK": {"AAA3": 1.0}, "FII": {"CCC11": 1.0}},
    })
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0), _asset("CCC11", "FII", 10.0)])

    r = c.post("/api/plan", json={"aporte": 1000.0, "min_ticket": 10.0}).json()
    assert r["targets_by_class"] == {"STOCK": 0.5, "FII": 0.3, "ETF": 0.2, "BDR": 0.0}
    # e o dinheiro segue a meta salva: carteira vazia, needs 500 (STOCK) e 300 (FII) -> 5:3
    aaa = next(x for x in r["ranking"] if x["ticker"] == "AAA3")["suggested"]
    ccc = next(x for x in r["ranking"] if x["ticker"] == "CCC11")["suggested"]
    assert abs(aaa["invested_exact"] - 625.0) < 15.0   # 1000 × 5/8
    assert abs(ccc["invested_exact"] - 375.0) < 15.0   # 1000 × 3/8


def test_request_targets_still_override_preferences(authed_client, monkeypatch):
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.5, "FII": 0.5},
        "class_targets": {"STOCK": {"AAA3": 1.0}},
    })
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])
    r = c.post("/api/plan", json={
        "aporte": 100.0, "min_ticket": 10.0, "targets": {"STOCK": 1.0},
    }).json()
    assert r["targets_by_class"] == {"STOCK": 1.0}


def test_zero_target_class_gets_no_missing_composition_warning(authed_client, monkeypatch):
    """BDR com meta 0% não está 'faltando composição' — não faz parte da carteira alvo."""
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.6, "FII": 0.4, "ETF": 0.0, "BDR": 0.0},
        "class_targets": {"STOCK": {"AAA3": 1.0}},
    })
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])
    r = c.post("/api/plan", json={"aporte": 100.0, "min_ticket": 10.0}).json()
    assert r["classes_skipped"] == ["FII"]  # FII tem meta 40% e nenhuma cesta: avisa
    assert not any("BDR" in w for w in r["warnings"])
    assert not any("ETF" in w for w in r["warnings"])


# --- rótulos por dimensão -----------------------------------------------------------

def test_labels_require_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_PASSWORD", "pw")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    get_settings.cache_clear()
    get_db.cache_clear()
    c = TestClient(create_app(), base_url="http://testserver")
    assert c.get("/api/labels").status_code == 401
    get_settings.cache_clear()
    get_db.cache_clear()


def test_labels_seeded_on_first_get(authed_client):
    indexers = authed_client.get("/api/labels?dimension=indexer").json()
    codes = {i["code"] for i in indexers}
    assert {"CDI", "SELIC", "IPCA", "PREFIXADO", "LCI", "LCA", "POUPANCA"} <= codes
    assert all(i["builtin"] for i in indexers)


def test_label_create_and_builtin_is_protected(authed_client):
    c = authed_client
    novo = c.post("/api/labels", json={"dimension": "indexer", "code": "cdb 110", "name": "CDB 110% CDI"})
    assert novo.status_code == 200 and novo.json()["code"] == "CDB_110"
    assert c.delete(f"/api/labels/{novo.json()['id']}").status_code == 200

    cdi = next(i for i in c.get("/api/labels?dimension=indexer").json() if i["code"] == "CDI")
    assert c.delete(f"/api/labels/{cdi['id']}").status_code == 422  # embutido não sai


def test_assignment_roundtrip_and_weight_validation(authed_client):
    c = authed_client
    geo = {g["code"]: g["id"] for g in c.get("/api/labels?dimension=geography").json()}

    ruim = c.put("/api/labels/assignments", json={
        "subject_type": "ticker", "subject_id": "AAA11", "dimension": "geography",
        "items": [{"label_id": geo["BR"], "weight": 0.6}, {"label_id": geo["INTL"], "weight": 0.6}],
    })
    assert ruim.status_code == 422

    ok = c.put("/api/labels/assignments", json={
        "subject_type": "ticker", "subject_id": "aaa11", "dimension": "geography",
        "items": [{"label_id": geo["INTL"], "weight": 0.6}, {"label_id": geo["BR"], "weight": 0.4}],
    })
    assert ok.status_code == 200
    assert {r["code"]: r["weight"] for r in ok.json()} == {"INTL": 0.6, "BR": 0.4}

    lido = c.get("/api/labels/assignments?dimension=geography&subject_type=ticker&subject_id=AAA11")
    assert {r["code"] for r in lido.json()} == {"BR", "INTL"}
    assert all(r["source"] == "user" for r in lido.json())


def test_assignments_include_defaults_distinguishes_inherited(authed_client):
    """A UI precisa saber o que ela herdou do mapa curado e o que o usuário escolheu."""
    c = authed_client
    geo = {g["code"]: g["id"] for g in c.get("/api/labels?dimension=geography").json()}
    c.put("/api/labels/assignments", json={
        "subject_type": "ticker", "subject_id": "BOVA11", "dimension": "geography",
        "items": [{"label_id": geo["INTL"]}],
    })
    r = c.get(
        "/api/labels/assignments?dimension=geography&subject_type=ticker"
        "&subjects=BOVA11,IVVB11,ZZZZ3&include_defaults=true"
    ).json()
    por_ticker = {x["subject_id"]: x for x in r}
    assert por_ticker["BOVA11"]["code"] == "INTL" and por_ticker["BOVA11"]["source"] == "user"
    assert por_ticker["IVVB11"]["code"] == "INTL" and por_ticker["IVVB11"]["source"] == "curated"
    assert por_ticker["ZZZZ3"]["code"] == "BR" and por_ticker["ZZZZ3"]["source"] == "fallback"


def test_clear_assignments_route(authed_client):
    c = authed_client
    geo = {g["code"]: g["id"] for g in c.get("/api/labels?dimension=geography").json()}
    c.put("/api/labels/assignments", json={
        "subject_type": "ticker", "subject_id": "AAA11", "dimension": "geography",
        "items": [{"label_id": geo["BR"]}],
    })
    assert c.delete(
        "/api/labels/assignments?subject_type=ticker&subject_id=AAA11&dimension=geography"
    ).status_code == 200
    assert c.get(
        "/api/labels/assignments?subject_type=ticker&subject_id=AAA11"
    ).json() == []


# --- renda fixa: o que conta na carteira ---------------------------------------------

def _conta(c, nome, **extra):
    body = {"name": nome, "liquidity": "immediate", **extra}
    return c.post("/api/fixed-income/accounts", json=body)


def _saldo(c, aid, valor, quando="2026-06-01"):
    return c.post(
        f"/api/fixed-income/accounts/{aid}/entries",
        json={"kind": "balance", "amount": valor, "entry_date": quando},
    )


def test_conta_do_ir_rende_na_reserva_e_nao_entra_na_carteira(authed_client, _stub_cdi):
    """Caso canônico: a provisão do IR aparece na Reserva, com rendimento, e em lugar
    nenhum da Carteira — nem influenciando o aporte."""
    c = authed_client
    selic = _conta(c, "Tesouro Selic", counts_in_portfolio=True).json()
    lci = _conta(c, "LCI 2 anos", counts_in_portfolio=True, liquidity="locked",
                 redeem_days=730).json()
    ir = _conta(c, "Provisão IR 2027", purpose="earmarked").json()

    _saldo(c, selic["id"], 30_000.0, "2026-01-05")
    _saldo(c, selic["id"], 31_200.0, "2026-06-01")
    _saldo(c, lci["id"], 20_000.0, "2026-01-05")
    _saldo(c, ir["id"], 5_000.0, "2026-01-05")
    _saldo(c, ir["id"], 5_180.0, "2026-06-01")

    s = c.get("/api/fixed-income/summary").json()
    assert s["total_balance"] == 56_380.0          # tudo que existe na aba Reserva
    assert s["portfolio_balance"] == 51_200.0      # Selic + LCI (o IR fica de fora)
    assert s["liquid_balance"] == 31_200.0         # só a Selic satisfaz o piso
    assert s["excluded_balance"] == 5_180.0        # o IR, com o motivo no `purpose`

    contas = {a["name"]: a for a in s["accounts"]}
    assert contas["Provisão IR 2027"]["in_portfolio"] is False
    assert contas["Provisão IR 2027"]["purpose"] == "earmarked"
    # e continua sendo uma conta normal na Reserva: rendimento calculado
    assert contas["Provisão IR 2027"]["history_yield_annual"] is not None
    assert contas["LCI 2 anos"]["in_portfolio"] is True and contas["LCI 2 anos"]["redeem_days"] == 730


def test_earmarked_nao_pode_contar_na_carteira(authed_client, _stub_cdi):
    c = authed_client
    ruim = _conta(c, "IR", purpose="earmarked", counts_in_portfolio=True)
    assert ruim.status_code == 422

    # e não dá para chegar lá em dois passos, cada um válido isoladamente
    aid = _conta(c, "IR", counts_in_portfolio=True).json()["id"]
    virou = c.patch(f"/api/fixed-income/accounts/{aid}", json={"purpose": "earmarked"})
    assert virou.status_code == 422
    assert c.get("/api/fixed-income/summary").json()["accounts"][0]["purpose"] == "investment"


def test_liquidez_e_obrigatoria_no_cadastro_novo(authed_client, _stub_cdi):
    sem = authed_client.post("/api/fixed-income/accounts", json={"name": "CDB sem resposta"})
    assert sem.status_code == 422
    assert "liquidity" in sem.text


def test_conta_pode_ser_desmarcada_da_carteira(authed_client, _stub_cdi):
    c = authed_client
    aid = _conta(c, "CDB", counts_in_portfolio=True).json()["id"]
    _saldo(c, aid, 1_000.0)
    assert c.get("/api/fixed-income/summary").json()["portfolio_balance"] == 1_000.0
    c.patch(f"/api/fixed-income/accounts/{aid}", json={"counts_in_portfolio": False})
    s = c.get("/api/fixed-income/summary").json()
    assert s["portfolio_balance"] == 0.0 and s["total_balance"] == 1_000.0


# --- classe RENDA_FIXA e cesta de indexadores -----------------------------------------

def _tag(c, code):
    return next(i for i in c.get("/api/labels?dimension=indexer").json() if i["code"] == code)["id"]


def _bucket(c, code):
    return next(i for i in c.get("/api/labels?dimension=bucket").json() if i["code"] == code)["id"]


def test_renda_fixa_e_classe_valida_na_carteira_alvo(authed_client):
    """Os itens da cesta são tags de indexador, não tickers — mesma aritmética, outro item."""
    c = authed_client
    ok = c.put("/api/preferences", json={
        "targets": {"STOCK": 0.6, "FII": 0.2, "ETF": 0.0, "BDR": 0.0, "RENDA_FIXA": 0.2},
        "class_targets": {"RENDA_FIXA": {"SELIC": 0.7, "IPCA": 0.3}},
    })
    assert ok.status_code == 200
    assert c.get("/api/preferences").json()["class_targets"]["RENDA_FIXA"] == {
        "SELIC": 0.7, "IPCA": 0.3
    }


def test_cesta_de_renda_fixa_ainda_precisa_fechar_100(authed_client):
    ruim = authed_client.put(
        "/api/preferences", json={"class_targets": {"RENDA_FIXA": {"SELIC": 0.5, "IPCA": 0.2}}}
    )
    assert ruim.status_code == 422


def test_indexers_soma_contas_por_tag_e_expoe_o_gap(authed_client, _stub_cdi, monkeypatch):
    c = authed_client
    selic = _conta(c, "Tesouro Selic", counts_in_portfolio=True).json()
    lci = _conta(c, "LCI", counts_in_portfolio=True, liquidity="locked").json()
    _saldo(c, selic["id"], 30_000.0)
    _saldo(c, lci["id"], 10_000.0)
    c.put("/api/labels/assignments", json={
        "subject_type": "fi_account", "subject_id": str(selic["id"]), "dimension": "indexer",
        "items": [{"label_id": _tag(c, "SELIC")}],
    })
    c.put("/api/labels/assignments", json={
        "subject_type": "fi_account", "subject_id": str(lci["id"]), "dimension": "indexer",
        "items": [{"label_id": _tag(c, "LCI")}],
    })
    c.put("/api/preferences", json={"class_targets": {"RENDA_FIXA": {"SELIC": 0.5, "LCI": 0.5}}})

    r = c.get("/api/fixed-income/indexers").json()
    por_code = {i["code"]: i for i in r["items"]}
    assert r["total"] == 40_000.0
    assert por_code["SELIC"]["value"] == 30_000.0 and por_code["SELIC"]["gap"] == -10_000.0
    assert por_code["LCI"]["value"] == 10_000.0 and por_code["LCI"]["gap"] == 10_000.0
    # Ghostfolio indisponível no teste: a resposta continua útil e diz o que faltou
    assert any("carteira" in w for w in r["warnings"])


def test_indexers_mostra_a_conta_sem_tag_em_vez_de_esconde_la(authed_client, _stub_cdi):
    c = authed_client
    acc = _conta(c, "CDB sem tag", counts_in_portfolio=True).json()
    _saldo(c, acc["id"], 7_000.0)
    r = c.get("/api/fixed-income/indexers").json()
    residual = next(i for i in r["items"] if i["code"] == "SEM_INDEXADOR")
    assert residual["value"] == 7_000.0
    assert any("indexador" in w for w in r["warnings"])


def test_indexers_ignora_conta_nao_marcada_e_earmarked(authed_client, _stub_cdi):
    c = authed_client
    fora = _conta(c, "Conta corrente").json()          # não marcada
    ir = _conta(c, "Provisão IR", purpose="earmarked").json()
    _saldo(c, fora["id"], 1_000.0)
    _saldo(c, ir["id"], 2_000.0)
    assert c.get("/api/fixed-income/indexers").json()["total"] == 0.0


def test_indexers_inclui_etf_atribuido_ao_bucket_renda_fixa(authed_client, _stub_cdi, monkeypatch):
    """Um ETF de renda fixa vira item da cesta ao lado de um CDB — é a precedência do
    override de bucket sobre a classificação automática."""
    from app.models.portfolio import Allocations, Portfolio, Position

    c = authed_client
    cdb = _conta(c, "CDB", counts_in_portfolio=True).json()
    _saldo(c, cdb["id"], 20_000.0)
    c.put("/api/labels/assignments", json={
        "subject_type": "fi_account", "subject_id": str(cdb["id"]), "dimension": "indexer",
        "items": [{"label_id": _tag(c, "CDI")}],
    })
    c.put("/api/labels/assignments", json={
        "subject_type": "ticker", "subject_id": "ZZZZ11", "dimension": "bucket",
        "items": [{"label_id": _bucket(c, "RENDA_FIXA")}],
    })
    c.put("/api/labels/assignments", json={
        "subject_type": "ticker", "subject_id": "ZZZZ11", "dimension": "indexer",
        "items": [{"label_id": _tag(c, "IPCA")}],
    })

    async def carteira(gf, cache, overrides=None):
        assert overrides == {"ZZZZ11": "RENDA_FIXA"}  # o override chega até a classificação
        return Portfolio(
            total_value=8_000.0, as_of="2026-06-01T00:00:00Z", allocations=Allocations(),
            positions=[Position(
                ticker="ZZZZ11", asset_class="RENDA_FIXA", value=8_000.0, weight=1.0,
            )],
        )

    monkeypatch.setattr("app.api.routes_fixed_income.get_enriched_portfolio", carteira)
    r = c.get("/api/fixed-income/indexers").json()
    por_code = {i["code"]: i["value"] for i in r["items"]}
    assert por_code == {"CDI": 20_000.0, "IPCA": 8_000.0}
    assert r["total"] == 28_000.0
    assert r["warnings"] == []


def test_plan_avisa_renda_fixa_com_meta_e_sem_indexador(authed_client, monkeypatch):
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.8, "RENDA_FIXA": 0.2},
        "class_targets": {"STOCK": {"AAA3": 1.0}},
    })
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])
    r = c.post("/api/plan", json={"aporte": 1000.0, "min_ticket": 10.0}).json()
    assert any("indexador" in w for w in r["warnings"])
    # e a renda fixa não entra no alocador de cotas
    assert r["classes_applied"] == ["STOCK"]
