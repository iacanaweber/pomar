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
    assert any("No peso-alvo ou acima" in x for x in bbb["reasons"])
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
    assert any("abaixo do alvo em" in x for x in bbb["reasons"])
    assert any("já está no peso-alvo da carteira" in x for x in bbb["reasons"])
    assert not any("No peso-alvo ou acima" in x for x in bbb["reasons"])
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
    assert any("carteira" in w.lower() for w in r["warnings"])


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


# --- composição do patrimônio (dimensões secundárias) ---------------------------------

def test_exposure_inclui_a_renda_fixa_marcada(authed_client, _stub_cdi, monkeypatch):
    from app.models.portfolio import Allocations, Portfolio, Position

    c = authed_client
    conta = _conta(c, "Tesouro Selic", counts_in_portfolio=True).json()
    fora = _conta(c, "Conta corrente").json()
    _saldo(c, conta["id"], 30_000.0)
    _saldo(c, fora["id"], 9_000.0)

    async def carteira(gf, cache, overrides=None):
        return Portfolio(
            total_value=70_000.0, as_of="2026-06-01T00:00:00Z", allocations=Allocations(),
            positions=[
                Position(ticker="AAA3", asset_class="STOCK", sector="Bancos",
                         value=50_000.0, weight=0.71),
                Position(ticker="IVVB11", asset_class="ETF", sector="Exterior",
                         value=20_000.0, weight=0.29),
            ],
        )

    monkeypatch.setattr("app.api.routes_portfolio.get_enriched_portfolio", carteira)
    r = c.get("/api/portfolio/exposure").json()
    assert r["total"] == 100_000.0  # 70k de RV + 30k da conta marcada (a outra fica fora)
    assert r["rv_total"] == 70_000.0 and r["rf_total"] == 30_000.0

    dims = {d["dimension"]: {i["code"]: i for i in d["items"]} for d in r["dimensions"]}
    assert dims["class"]["RENDA_FIXA"]["value"] == 30_000.0
    assert dims["class"]["RENDA_FIXA"]["name"] == "Renda fixa"
    # IVVB11 é internacional pelo mapa curado; a conta de renda fixa é brasileira
    assert dims["geography"]["INTL"]["value"] == 20_000.0
    assert dims["geography"]["BR"]["value"] == 80_000.0
    assert dims["geography"]["BR"]["pct"] == 0.8


def test_exposure_mostra_meta_e_desvio_sem_afetar_a_compra(authed_client, _stub_cdi, monkeypatch):
    from app.models.portfolio import Allocations, Portfolio, Position

    c = authed_client
    assert c.put("/api/preferences", json={
        "dimension_targets": {"geography": {"INTL": 0.3}},
    }).status_code == 200

    async def carteira(gf, cache, overrides=None):
        return Portfolio(
            total_value=100_000.0, as_of="2026-06-01T00:00:00Z", allocations=Allocations(),
            positions=[Position(ticker="IVVB11", asset_class="ETF", value=20_000.0, weight=0.2),
                       Position(ticker="AAA3", asset_class="STOCK", value=80_000.0, weight=0.8)],
        )

    monkeypatch.setattr("app.api.routes_portfolio.get_enriched_portfolio", carteira)
    geo = next(d for d in c.get("/api/portfolio/exposure").json()["dimensions"]
               if d["dimension"] == "geography")
    intl = next(i for i in geo["items"] if i["code"] == "INTL")
    assert intl["target_pct"] == 0.3 and intl["deviation_pp"] == -10.0

    # e a meta não entra em lugar nenhum do plano
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])
    c.put("/api/preferences", json={"class_targets": {"STOCK": {"AAA3": 1.0}}})
    plano = c.post("/api/plan", json={"aporte": 1000.0, "classes": ["STOCK"],
                                      "min_ticket": 10.0}).json()
    assert not any("INTL" in w or "geogra" in w.lower() for w in plano["warnings"])


def test_dimensao_bucket_nao_aceita_meta_secundaria(authed_client):
    """Meta vinculante em duas dimensões independentes é um sistema sobredeterminado."""
    r = authed_client.put(
        "/api/preferences", json={"dimension_targets": {"bucket": {"STOCK": 0.5}}}
    )
    assert r.status_code == 422


def test_meta_secundaria_acima_de_100_e_recusada(authed_client):
    r = authed_client.put(
        "/api/preferences", json={"dimension_targets": {"geography": {"BR": 0.8, "INTL": 0.5}}}
    )
    assert r.status_code == 422
    # abaixo de 100% é legítimo: "quero 20% internacional" e sem opinião sobre o resto
    ok = authed_client.put(
        "/api/preferences", json={"dimension_targets": {"geography": {"INTL": 0.2}}}
    )
    assert ok.status_code == 200


def test_exposure_degrada_sem_ghostfolio(authed_client, _stub_cdi):
    """A renda fixa continua correta e a resposta diz o que ficou de fora."""
    c = authed_client
    conta = _conta(c, "CDB", counts_in_portfolio=True).json()
    _saldo(c, conta["id"], 10_000.0)
    r = c.get("/api/portfolio/exposure").json()
    assert r["total"] == 10_000.0 and r["rv_total"] == 0.0
    assert any("carteira" in w.lower() for w in r["warnings"])


# --- ativos fora do alvo no plano -----------------------------------------------------

def _carteira(monkeypatch, posicoes, total=None):
    from app.models.portfolio import Allocations, Portfolio, Position

    pos = [Position(ticker=t, asset_class=c, value=v, weight=0.0) for t, c, v in posicoes]
    soma = total if total is not None else sum(p.value for p in pos)
    by_class: dict[str, float] = {}
    for p in pos:
        p.weight = p.value / soma if soma else 0.0
        by_class[p.asset_class] = by_class.get(p.asset_class, 0.0) + p.weight
    return Portfolio(
        total_value=soma, as_of="2026-06-01T00:00:00Z",
        allocations=Allocations(by_class=by_class), positions=pos,
    )


def test_plan_reports_legacy_value_and_gap_coverage(authed_client, monkeypatch):
    """Aritmética, não sugestão de venda: quanto do gap está parado fora da estratégia."""
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 1.0, "FII": 0.0, "ETF": 0.0, "BDR": 0.0},
        "class_targets": {"STOCK": {"AAA3": 1.0}},
    })
    _stub_plan_market(
        monkeypatch, [_asset("AAA3", "STOCK", 10.0)],
        portfolio=_carteira(monkeypatch, [("AAA3", "STOCK", 1_000.0), ("VELHO4", "STOCK", 500.0)]),
    )
    r = c.post("/api/plan", json={"aporte": 100.0, "min_ticket": 10.0}).json()
    assert r["legacy"] is not None
    assert r["legacy"]["value"] == 500.0
    assert r["legacy"]["tickers"] == ["VELHO4"]
    # gap = 100% de (1500 + 100) − (1000 comprados + 100 do aporte) = 500
    assert r["legacy"]["gap"] == 500.0
    assert r["legacy"]["gap_coverage"] == 1.0


def test_plan_without_legacy_has_no_summary(authed_client, monkeypatch):
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 1.0}, "class_targets": {"STOCK": {"AAA3": 1.0}},
    })
    _stub_plan_market(
        monkeypatch, [_asset("AAA3", "STOCK", 10.0)],
        portfolio=_carteira(monkeypatch, [("AAA3", "STOCK", 1_000.0)]),
    )
    r = c.post("/api/plan", json={"aporte": 100.0, "min_ticket": 10.0}).json()
    assert r["legacy"] is None


def test_plan_class_with_zero_target_becomes_legacy(authed_client, monkeypatch):
    """A situação real: a carteira alvo mudou, STOCK foi a 0% e as ações seguem compradas."""
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.0, "FII": 1.0, "ETF": 0.0, "BDR": 0.0},
        "class_targets": {"STOCK": {"AAA3": 1.0}, "FII": {"CCC11": 1.0}},
    })
    _stub_plan_market(
        monkeypatch, [_asset("CCC11", "FII", 10.0)],
        portfolio=_carteira(monkeypatch, [("AAA3", "STOCK", 700.0), ("CCC11", "FII", 300.0)]),
    )
    r = c.post("/api/plan", json={"aporte": 100.0, "classes": ["FII"], "min_ticket": 10.0}).json()
    assert r["legacy"]["tickers"] == ["AAA3"]
    assert r["legacy"]["value"] == 700.0
    # e nada de Infinity/NaN por causa do alvo zero
    import math
    assert all(math.isfinite(v) for v in (r["legacy"]["value"], r["legacy"]["gap"],
                                          r["legacy"]["gap_coverage"]))


def test_plan_legacy_without_gap_has_no_coverage(authed_client, monkeypatch):
    """Sem gap, 'cobriria 0%' se leria como 'não adiantaria nada' — daí o None.

    Com `legacy_in_total=false` os alvos incidem só sobre o capital alinhado, então uma
    carteira alinhada e no alvo não tem buraco a cobrir, por mais legado que exista.
    """
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 1.0}, "class_targets": {"STOCK": {"AAA3": 1.0}},
        "legacy_in_total": False,
    })
    _stub_plan_market(
        monkeypatch, [_asset("AAA3", "STOCK", 10.0)],
        portfolio=_carteira(monkeypatch, [("AAA3", "STOCK", 100_000.0), ("VELHO4", "STOCK", 500.0)]),
    )
    r = c.post("/api/plan", json={"aporte": 10.0, "min_ticket": 10.0}).json()
    assert r["legacy"]["value"] == 500.0
    assert r["legacy"]["gap"] == 0.0
    assert r["legacy"]["gap_coverage"] is None


def test_legacy_in_total_muda_a_base_dos_alvos(authed_client, monkeypatch):
    """O default mantém a carteira subalocada até a venda; o opt-out mira só o alinhado."""
    posicoes = [("AAA3", "STOCK", 1_000.0), ("VELHO4", "STOCK", 500.0)]
    c = authed_client

    c.put("/api/preferences", json={
        "targets": {"STOCK": 1.0}, "class_targets": {"STOCK": {"AAA3": 1.0}},
        "legacy_in_total": True,
    })
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)],
                      portfolio=_carteira(monkeypatch, posicoes))
    com = c.post("/api/plan", json={"aporte": 100.0, "min_ticket": 10.0}).json()
    # base 1500 + 100 = 1600; alinhado após a compra = 1100 => sobra buraco de 500
    assert com["legacy"]["gap"] == 500.0

    c.put("/api/preferences", json={"legacy_in_total": False})
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)],
                      portfolio=_carteira(monkeypatch, posicoes))
    sem = c.post("/api/plan", json={"aporte": 100.0, "min_ticket": 10.0}).json()
    # base 1000 + 100 = 1100; alinhado após a compra = 1100 => sem buraco
    assert sem["legacy"]["gap"] == 0.0


# --- cascata do aporte no plano -------------------------------------------------------

def test_plan_cascade_floor_then_weight_then_equities(authed_client, _stub_cdi, monkeypatch):
    """Os três degraus, em ordem, com a invariante de conservação verificada."""
    c = authed_client
    selic = _conta(c, "Tesouro Selic", counts_in_portfolio=True).json()
    _saldo(c, selic["id"], 9_000.0)
    c.put("/api/labels/assignments", json={
        "subject_type": "fi_account", "subject_id": str(selic["id"]), "dimension": "indexer",
        "items": [{"label_id": _tag(c, "SELIC")}],
    })
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.8, "RENDA_FIXA": 0.2, "FII": 0.0, "ETF": 0.0, "BDR": 0.0},
        "class_targets": {"STOCK": {"AAA3": 1.0}, "RENDA_FIXA": {"SELIC": 1.0}},
        "reserve_floor_amount": 10_000.0,
    })
    _stub_plan_market(
        monkeypatch, [_asset("AAA3", "STOCK", 10.0)],
        portfolio=_carteira(monkeypatch, [("AAA3", "STOCK", 40_000.0)]),
    )
    r = c.post("/api/plan", json={"aporte": 3_000.0, "min_ticket": 10.0}).json()

    fi = r["fixed_income"]
    assert fi is not None
    # piso 10.000 contra reserva líquida 9.000 => 1.000 no primeiro degrau
    assert fi["floor_part"] == 1_000.0
    # patrimônio resultante = 40.000 + 9.000 + 3.000 = 52.000; alvo RF 20% = 10.400
    # após o piso a classe tem 10.000 => faltam 400 no segundo degrau
    assert fi["weight_part"] == 400.0
    assert fi["directed_now"] == 1_400.0
    assert fi["by_indexer"][0]["code"] == "SELIC"
    assert fi["by_indexer"][0]["account_id"] == selic["id"]
    assert fi["by_indexer"][0]["account_name"] == "Tesouro Selic"

    comprado = sum(x["suggested"]["invested_exact"] for x in r["ranking"] if x["suggested"])
    assert abs(fi["directed_now"] + comprado + r["unallocated"] - 3_000.0) < 0.01


def test_plan_fixed_income_above_target_sends_everything_to_equities(
    authed_client, _stub_cdi, monkeypatch
):
    """Renda fixa acima do alvo: gap zero, aporte inteiro para a RV, sem erro."""
    c = authed_client
    acc = _conta(c, "CDB", counts_in_portfolio=True).json()
    _saldo(c, acc["id"], 50_000.0)
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.9, "RENDA_FIXA": 0.1, "FII": 0.0, "ETF": 0.0, "BDR": 0.0},
        "class_targets": {"STOCK": {"AAA3": 1.0}, "RENDA_FIXA": {"CDI": 1.0}},
    })
    _stub_plan_market(
        monkeypatch, [_asset("AAA3", "STOCK", 10.0)],
        portfolio=_carteira(monkeypatch, [("AAA3", "STOCK", 10_000.0)]),
    )
    r = c.post("/api/plan", json={"aporte": 1_000.0, "min_ticket": 10.0}).json()

    assert r["fixed_income"]["gap_brl"] == 0.0
    assert r["fixed_income"]["directed_now"] == 0.0
    assert "aporte inteiro" in r["fixed_income"]["note"]
    # e nenhum aviso de erro por causa disso
    assert not any("renda fixa" in w.lower() and "erro" in w.lower() for w in r["warnings"])
    comprado = sum(x["suggested"]["invested_exact"] for x in r["ranking"] if x["suggested"])
    assert abs(comprado + r["unallocated"] - 1_000.0) < 0.01


def test_plan_gap_is_reported_in_brl_and_pp(authed_client, _stub_cdi, monkeypatch):
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.8, "RENDA_FIXA": 0.2, "FII": 0.0, "ETF": 0.0, "BDR": 0.0},
        "class_targets": {"STOCK": {"AAA3": 1.0}, "RENDA_FIXA": {"CDI": 1.0}},
    })
    _stub_plan_market(
        monkeypatch, [_asset("AAA3", "STOCK", 10.0)],
        portfolio=_carteira(monkeypatch, [("AAA3", "STOCK", 9_000.0)]),
    )
    r = c.post("/api/plan", json={"aporte": 1_000.0, "min_ticket": 10.0}).json()
    fi = r["fixed_income"]
    # patrimônio resultante = 10.000; alvo 20% = 2.000; atual 0 => gap 2.000 = 20 p.p.
    assert fi["gap_brl"] == 2_000.0
    assert fi["gap_pp"] == 20.0
    assert fi["directed_now"] == 1_000.0  # o aporte inteiro, e ainda falta


def test_plan_renda_fixa_no_patrimonio_muda_o_alvo_da_bolsa(authed_client, _stub_cdi, monkeypatch):
    """A base dos alvos passa a incluir a renda fixa marcada: sem isso, a bolsa pedia
    aporte calculado como se aquele dinheiro não existisse."""
    c = authed_client
    acc = _conta(c, "Tesouro Selic", counts_in_portfolio=True).json()
    _saldo(c, acc["id"], 50_000.0)
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.5, "RENDA_FIXA": 0.5, "FII": 0.0, "ETF": 0.0, "BDR": 0.0},
        "class_targets": {"STOCK": {"AAA3": 1.0}, "RENDA_FIXA": {"CDI": 1.0}},
    })
    _stub_plan_market(
        monkeypatch, [_asset("AAA3", "STOCK", 10.0)],
        portfolio=_carteira(monkeypatch, [("AAA3", "STOCK", 50_000.0)]),
    )
    r = c.post("/api/plan", json={"aporte": 1_000.0, "min_ticket": 10.0}).json()
    # 50k em ações e 50k em RF: a carteira já está 50/50 e o aporte se divide, não corre
    # para a bolsa como se o patrimônio fosse só os 50k de ações
    assert r["fixed_income"]["current_value"] == 50_000.0
    comprado = sum(x["suggested"]["invested_exact"] for x in r["ranking"] if x["suggested"])
    assert abs(r["fixed_income"]["directed_now"] + comprado + r["unallocated"] - 1_000.0) < 0.01


def test_plan_fixed_income_without_basket_still_instructs(authed_client, _stub_cdi, monkeypatch):
    """Sem cesta de indexadores, a instrução é o total: inventar um alvo seria pior."""
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.5, "RENDA_FIXA": 0.5, "FII": 0.0, "ETF": 0.0, "BDR": 0.0},
        "class_targets": {"STOCK": {"AAA3": 1.0}},
    })
    _stub_plan_market(
        monkeypatch, [_asset("AAA3", "STOCK", 10.0)],
        portfolio=_carteira(monkeypatch, [("AAA3", "STOCK", 10_000.0)]),
    )
    r = c.post("/api/plan", json={"aporte": 1_000.0, "min_ticket": 10.0}).json()
    assert r["fixed_income"]["directed_now"] == 1_000.0
    assert r["fixed_income"]["by_indexer"][0]["code"] == "SEM_INDEXADOR"
    assert any("indexador" in w for w in r["warnings"])


# --- curva de rendimento (TWR semanal) ------------------------------------------------

def test_performance_sem_serie_explica_em_vez_de_erro(authed_client):
    r = authed_client.get("/api/performance")
    assert r.status_code == 200
    d = r.json()
    assert d["points"] == []
    assert any("primeiro ponto é gravado" in w for w in d["warnings"])


def _semear_serie(client, monkeypatch, pontos):
    """Captura N semanas seguidas com valores controlados, sem rede."""
    from datetime import date
    from app.deps import get_db
    from app.services import weekly
    import asyncio

    class _GF:
        def __init__(self, acts): self._a = acts
        async def get_activities(self): return list(self._a)

    async def run():
        db = get_db()
        for quando, total, acts in pontos:
            def fake(gf, cache, overrides=None, _t=total):
                from app.models.portfolio import Allocations, Portfolio, Position
                async def inner():
                    return Portfolio(total_value=_t, as_of="2026-06-01T00:00:00Z",
                                     allocations=Allocations(),
                                     positions=[Position(ticker="AAA3", asset_class="STOCK",
                                                         value=_t, weight=1.0)])
                return inner()
            monkeypatch.setattr("app.services.portfolio_service.get_enriched_portfolio", fake)
            await weekly.capture_week(db, _GF(acts), cache=None, when=date.fromisoformat(quando))
    asyncio.get_event_loop().run_until_complete(run()) if False else asyncio.run(run())


def test_performance_devolve_twr_e_xirr_separados(authed_client, monkeypatch):
    """TWR compara com índice; XIRR responde 'quanto o MEU dinheiro rendeu' e por isso
    vem sozinho."""
    c = authed_client
    _semear_serie(c, monkeypatch, [
        ("2026-05-11", 10_000.0, []),
        ("2026-05-18", 10_500.0, []),
        ("2026-05-25", 11_025.0, []),
    ])
    d = c.get("/api/performance").json()
    assert len(d["points"]) == 3
    assert d["twr"] == pytest.approx(0.1025, abs=1e-6)  # 5% encadeado com 5%
    assert d["points"][0]["twr_cumulative"] == 0.0
    assert d["points"][-1]["twr_cumulative"] == pytest.approx(0.1025, abs=1e-6)
    assert d["current_value"] == 11_025.0


def test_performance_avisa_com_menos_de_quatro_pontos(authed_client, monkeypatch):
    c = authed_client
    _semear_serie(c, monkeypatch, [("2026-05-11", 10_000.0, []), ("2026-05-18", 10_100.0, [])])
    d = c.get("/api/performance").json()
    assert any("quatro pontos" in w for w in d["warnings"])


def test_performance_reporta_lacuna(authed_client, monkeypatch):
    c = authed_client
    _semear_serie(c, monkeypatch, [
        ("2026-05-11", 10_000.0, []),
        ("2026-05-25", 10_500.0, []),  # pula a semana W20
    ])
    d = c.get("/api/performance").json()
    assert d["gaps"] == ["2026-W20"]
    assert any("lacuna" in w for w in d["warnings"])


def test_performance_janela_recorta_a_serie(authed_client, monkeypatch):
    c = authed_client
    _semear_serie(c, monkeypatch, [
        ("2026-05-11", 10_000.0, []),
        ("2026-05-18", 10_500.0, []),
    ])
    d = c.get("/api/performance?window=3m").json()
    assert d["window"] == "3m"
    assert isinstance(d["points"], list)


def test_performance_expoe_os_pesos_do_composto(authed_client, monkeypatch):
    c = authed_client
    c.put("/api/preferences", json={
        "targets": {"STOCK": 0.6, "FII": 0.2, "RENDA_FIXA": 0.2, "ETF": 0.0, "BDR": 0.0},
    })
    _semear_serie(c, monkeypatch, [("2026-05-11", 10_000.0, []), ("2026-05-18", 10_500.0, [])])
    d = c.get("/api/performance").json()
    assert d["composite_weights"] == {"IBOV": 0.6, "IFIX": 0.2, "CDI": 0.2}


def test_performance_requires_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_PASSWORD", "pw")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    get_settings.cache_clear(); get_db.cache_clear()
    c = TestClient(create_app(), base_url="http://testserver")
    assert c.get("/api/performance").status_code == 401
    get_settings.cache_clear(); get_db.cache_clear()


def test_plan_teto_do_aporte_para_o_piso(authed_client, _stub_cdi, monkeypatch):
    """O caso do dono: aporte 2.000, teto em 50%, faltando 9.501 no piso.

    Sem o teto, o déficit come o aporte inteiro e a bolsa fica com zero — mês após mês.
    """
    c = authed_client
    c.put("/api/preferences", json={
        "class_targets": {"STOCK": {"AAA3": 1.0}},
        "reserve_floor_amount": 30_000.0,
    })
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])

    r = c.post("/api/plan", json={
        "aporte": 2_000.0, "classes": ["STOCK"], "min_ticket": 10.0,
        "reserve_current": 20_499.0, "reserve_floor_share": 0.5,
    }).json()

    assert r["reserve"]["gap"] == 9_501.0
    assert r["reserve"]["directed_now"] == 1_000.0
    assert "50% do aporte" in r["fixed_income"]["note"]
    bought = next(x for x in r["ranking"] if x["ticker"] == "AAA3")
    assert bought["suggested"]["invested_exact"] == 1_000.0


def test_plan_teto_em_zero_nao_desvia_e_explica(authed_client, _stub_cdi, monkeypatch):
    c = authed_client
    c.put("/api/preferences", json={
        "class_targets": {"STOCK": {"AAA3": 1.0}},
        "reserve_floor_amount": 30_000.0,
    })
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])

    r = c.post("/api/plan", json={
        "aporte": 1_000.0, "classes": ["STOCK"], "min_ticket": 10.0,
        "reserve_current": 20_000.0, "reserve_floor_share": 0.0,
    }).json()

    assert r["reserve"]["directed_now"] == 0.0
    # o silêncio esconderia a decisão de não cobrir o piso
    assert "Nada para o piso da reserva" in r["fixed_income"]["note"]
    assert next(x for x in r["ranking"] if x["ticker"] == "AAA3")["suggested"]["invested_exact"] == 1_000.0


def test_plan_teto_salvo_nas_preferencias_vale_sem_o_cliente_mandar(
    authed_client, _stub_cdi, monkeypatch
):
    """PWA com JS em cache manda PlanRequest sem o campo — a preferência tem que valer."""
    c = authed_client
    c.put("/api/preferences", json={
        "class_targets": {"STOCK": {"AAA3": 1.0}},
        "reserve_floor_amount": 30_000.0,
        "reserve_floor_share": 0.25,
    })
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])

    r = c.post("/api/plan", json={
        "aporte": 2_000.0, "classes": ["STOCK"], "min_ticket": 10.0, "reserve_current": 0.0,
    }).json()
    assert r["reserve"]["directed_now"] == 500.0


def test_plan_sem_teto_configurado_mantem_a_prioridade_absoluta(
    authed_client, _stub_cdi, monkeypatch
):
    """A garantia de que ninguém acorda com o plano diferente."""
    c = authed_client
    c.put("/api/preferences", json={
        "class_targets": {"STOCK": {"AAA3": 1.0}},
        "reserve_floor_amount": 30_000.0,
    })
    _stub_plan_market(monkeypatch, [_asset("AAA3", "STOCK", 10.0)])

    r = c.post("/api/plan", json={
        "aporte": 1_000.0, "classes": ["STOCK"], "min_ticket": 10.0,
        "reserve_current": 20_000.0,
    }).json()
    assert r["reserve"]["directed_now"] == 1_000.0
    # sem corte, a nota não ganha parêntese nenhum
    assert "máximo de" not in r["fixed_income"]["note"]
