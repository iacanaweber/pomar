"""Testes do motor de score: normalização, dados faltantes e estratégias."""
from __future__ import annotations

from app.models.market import Asset, Fundamentals
from app.models.portfolio import Allocations, Portfolio
from app.services.scoring import score_assets

WEIGHTS = {"valuation": 0.30, "dividend": 0.35, "rebalance": 0.20, "sector": 0.15}


def _portfolio() -> Portfolio:
    return Portfolio(
        total_value=10000.0,
        as_of="2026-06-15T00:00:00Z",
        allocations=Allocations(by_class={"STOCK": 0.8, "FII": 0.2}),
    )


def test_ranking_orders_by_composite_and_assigns_rank():
    assets = [
        Asset(ticker="BBAS3", asset_class="STOCK", sector="Bancos", price=28.0,
              fundamentals=Fundamentals(pvp=0.8, pl=4.0, dividend_yield=0.10),
              dividends_by_year={"2022": 2.5, "2023": 2.6, "2024": 2.7}),
        Asset(ticker="WEGE3", asset_class="STOCK", sector="Bens Industriais", price=40.0,
              fundamentals=Fundamentals(pvp=9.0, pl=30.0, dividend_yield=0.01),
              dividends_by_year={"2024": 0.4}),
    ]
    ranking = score_assets(assets, _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    assert ranking[0].ticker == "BBAS3"  # mais barato, paga mais, setor perene
    assert ranking[0].rank == 1
    assert ranking[1].rank == 2
    assert 0.0 <= ranking[0].composite_score <= 1.0


def test_missing_data_redistributes_weight_and_reports_completeness():
    # ativo sem nenhum fundamento: só rebalance/sector aplicáveis
    assets = [
        Asset(ticker="XXXX3", asset_class="STOCK", sector=None, price=10.0),
        Asset(ticker="BBAS3", asset_class="STOCK", sector="Bancos", price=28.0,
              fundamentals=Fundamentals(pvp=0.8, pl=4.0, dividend_yield=0.10),
              dividends_by_year={"2023": 2.6, "2024": 2.7}),
    ]
    ranking = score_assets(assets, _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    xxxx = next(r for r in ranking if r.ticker == "XXXX3")
    # pesos das métricas disponíveis devem somar ~1 (renormalizados)
    total_w = sum(m.weight for m in xxxx.metrics if m.available)
    assert abs(total_w - 1.0) < 1e-6
    # nenhuma métrica indisponível recebe contribuição
    assert all(m.contribution is None for m in xxxx.metrics if not m.available)
    assert "/" in xxxx.data_completeness


def test_bazin_margin_positive_when_cheap_relative_to_dividends():
    # dividendo médio 2.0; preço-teto = 2/0.06 = 33.3; preço 20 => margem positiva.
    # >= 3 anos pagos (BAZIN_MIN_PAID_YEARS).
    a = Asset(ticker="TEST3", asset_class="STOCK", sector="Energia", price=20.0,
              fundamentals=Fundamentals(pvp=1.0, pl=8.0, dividend_yield=0.10),
              dividends_by_year={"2022": 2.0, "2023": 2.0, "2024": 2.0})
    ranking = score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    bazin = next(m for m in ranking[0].metrics if m.key == "bazin_ceiling")
    assert bazin.raw_value is not None and bazin.raw_value > 0


def test_bazin_unavailable_without_min_paid_years():
    # só 2 anos pagos => Bazin indisponível (não derivar de média curta/circular)
    a = Asset(ticker="TEST3", asset_class="STOCK", sector="Energia", price=20.0,
              fundamentals=Fundamentals(pvp=1.0, pl=8.0, dividend_yield=0.10),
              dividends_by_year={"2023": 2.0, "2024": 2.0})
    ranking = score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    bazin = next(m for m in ranking[0].metrics if m.key == "bazin_ceiling")
    assert bazin.available is False and bazin.raw_value is None


def test_bazin_mean_ignores_unpaid_years():
    # 3 anos pagos de 2.0 e um ano "0" (pulo) não deve deflacionar a média.
    paid_only = Asset(ticker="AAA3", asset_class="STOCK", price=20.0,
                      fundamentals=Fundamentals(pvp=1.0, pl=8.0),
                      dividends_by_year={"2022": 2.0, "2023": 2.0, "2024": 2.0})
    with_zero = Asset(ticker="BBB3", asset_class="STOCK", price=20.0,
                      fundamentals=Fundamentals(pvp=1.0, pl=8.0),
                      dividends_by_year={"2021": 2.0, "2022": 0.0, "2023": 2.0, "2024": 2.0})
    r = score_assets([paid_only, with_zero], _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    m_a = next(m for m in next(x for x in r if x.ticker == "AAA3").metrics if m.key == "bazin_ceiling")
    m_b = next(m for m in next(x for x in r if x.ticker == "BBB3").metrics if m.key == "bazin_ceiling")
    # ambos têm média de proventos pagos = 2.0 => mesma margem (zero não conta)
    assert abs((m_a.raw_value or 0) - (m_b.raw_value or 0)) < 1e-9


def test_graham_anchor_zero_above_ceiling():
    # P/L×P/VP muito acima de 22,5 => margem Graham zerada (Graham rejeita)
    cheap = Asset(ticker="CHEAP3", asset_class="STOCK", price=10.0,
                  fundamentals=Fundamentals(pvp=0.8, pl=5.0))   # produto 4.0
    pricey = Asset(ticker="PRICEY3", asset_class="STOCK", price=10.0,
                   fundamentals=Fundamentals(pvp=9.0, pl=30.0))  # produto 270
    r = score_assets([cheap, pricey], _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    g_cheap = next(m for m in next(x for x in r if x.ticker == "CHEAP3").metrics if m.key == "graham")
    g_pricey = next(m for m in next(x for x in r if x.ticker == "PRICEY3").metrics if m.key == "graham")
    assert g_pricey.normalized == 0.0  # acima do teto
    assert (g_cheap.normalized or 0) > 0.8  # bem abaixo do teto


def test_pl_negative_is_not_a_discount():
    # P/L negativo (prejuízo) não pode virar "o mais barato" — fica indisponível
    a = Asset(ticker="LOSS3", asset_class="STOCK", price=10.0,
              fundamentals=Fundamentals(pvp=1.0, pl=-5.0))
    ranking = score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    pl = next(m for m in ranking[0].metrics if m.key == "pl")
    assert pl.available is False and pl.raw_value is None


def test_number_of_graham_uses_lpa_vpa():
    # intrínseco = sqrt(22,5*2*10) = sqrt(450) ≈ 21,2; preço 10 => margem ~0,53
    a = Asset(ticker="GR3", asset_class="STOCK", price=10.0,
              fundamentals=Fundamentals(pvp=1.0, pl=8.0, lpa=2.0, vpa=10.0))
    ranking = score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    gi = next(m for m in ranking[0].metrics if m.key == "graham_intrinsic")
    assert gi.available is True and (gi.raw_value or 0) > 0.4


def test_percentile_excludes_self_so_worst_is_low():
    # 3 ativos com P/VP distintos; o de maior P/VP (pior) deve ficar perto de 0, não 1/3
    assets = [
        Asset(ticker="A3", asset_class="STOCK", price=10.0, fundamentals=Fundamentals(pvp=0.5, pl=5.0)),
        Asset(ticker="B3", asset_class="STOCK", price=10.0, fundamentals=Fundamentals(pvp=1.0, pl=5.0)),
        Asset(ticker="C3", asset_class="STOCK", price=10.0, fundamentals=Fundamentals(pvp=3.0, pl=5.0)),
    ]
    r = score_assets(assets, _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    worst = next(m for m in next(x for x in r if x.ticker == "C3").metrics if m.key == "pvp")
    assert worst.normalized == 0.0  # pior dos 3, excluindo a si mesmo


# --- Eixo de risco / qualidade (anti value-trap) ---

def test_loss_making_gets_red_flag_and_penalty():
    a = Asset(ticker="LOSS3", asset_class="STOCK", price=10.0,
              fundamentals=Fundamentals(pvp=0.5, pl=-5.0, dividend_yield=0.15))
    r = score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS)[0]
    assert r.quality_factor <= 0.5
    assert any("prejuízo" in f.lower() for f in r.red_flags)
    assert r.risk_level == "vermelho"


def test_high_debt_penalizes_quality():
    healthy = Asset(ticker="OK3", asset_class="STOCK", price=10.0,
                    fundamentals=Fundamentals(pvp=1.0, pl=8.0, dividend_yield=0.08, net_debt_to_ebitda=1.0))
    levered = Asset(ticker="DEBT3", asset_class="STOCK", price=10.0,
                    fundamentals=Fundamentals(pvp=1.0, pl=8.0, dividend_yield=0.08, net_debt_to_ebitda=6.0))
    r = score_assets([healthy, levered], _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    ok = next(x for x in r if x.ticker == "OK3")
    debt = next(x for x in r if x.ticker == "DEBT3")
    assert debt.quality_factor < ok.quality_factor
    assert any("ndividamento" in f for f in debt.red_flags)


def test_payout_over_100_flags():
    a = Asset(ticker="PAY3", asset_class="STOCK", price=10.0,
              fundamentals=Fundamentals(pvp=1.0, pl=8.0, lpa=1.0),
              dividends_by_year={"2022": 1.5, "2023": 1.5, "2024": 1.5})
    r = score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS)[0]
    assert any("ayout" in f for f in r.red_flags)
    assert r.quality_factor <= 0.6


def test_healthy_asset_is_green_no_flags():
    a = Asset(ticker="GOOD3", asset_class="STOCK", sector="Bancos", price=20.0,
              fundamentals=Fundamentals(pvp=0.8, pl=6.0, dividend_yield=0.09, lpa=3.0, vpa=25.0,
                                        net_debt_to_ebitda=1.0),
              dividends_by_year={"2022": 2.0, "2023": 2.1, "2024": 2.2})
    r = score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS)[0]
    assert r.quality_factor == 1.0
    assert r.risk_level == "verde"
    assert r.red_flags == []


def test_value_trap_sinks_below_healthy():
    # "barato + paga muito" mas endividado e com prejuízo deve cair abaixo de um saudável
    trap = Asset(ticker="TRAP3", asset_class="STOCK", sector="Bancos", price=10.0,
                 fundamentals=Fundamentals(pvp=0.4, pl=-3.0, dividend_yield=0.18, net_debt_to_ebitda=7.0))
    good = Asset(ticker="SOLID3", asset_class="STOCK", sector="Bancos", price=20.0,
                 fundamentals=Fundamentals(pvp=0.9, pl=7.0, dividend_yield=0.08, lpa=3.0, vpa=22.0,
                                           net_debt_to_ebitda=1.0),
                 dividends_by_year={"2022": 1.6, "2023": 1.7, "2024": 1.8})
    r = score_assets([trap, good], _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    assert r[0].ticker == "SOLID3"  # saudável vence a armadilha de valor


# --- Estratégias v2: filtros de elegibilidade ---

def test_graham_strategy_excludes_ineligible():
    loss = Asset(ticker="L3", asset_class="STOCK", price=10.0,
                 fundamentals=Fundamentals(pvp=1.0, pl=-2.0))
    pricey = Asset(ticker="P3", asset_class="STOCK", price=10.0,
                   fundamentals=Fundamentals(pvp=5.0, pl=30.0))  # 150 > 22,5
    cheap = Asset(ticker="C3", asset_class="STOCK", price=10.0,
                  fundamentals=Fundamentals(pvp=0.8, pl=5.0, current_ratio=2.0))  # 4,0
    r = score_assets([loss, pricey, cheap], _portfolio(), {"STOCK": 1.0}, WEIGHTS, strategy="graham")
    by = {x.ticker: x for x in r}
    assert by["L3"].composite_score == 0.0
    assert by["P3"].composite_score == 0.0
    assert by["C3"].composite_score > 0.0
    assert any("Graham" in f for f in by["L3"].red_flags)


def test_equilibrado_does_not_filter():
    pricey = Asset(ticker="P3", asset_class="STOCK", price=10.0,
                   fundamentals=Fundamentals(pvp=5.0, pl=30.0))
    r = score_assets([pricey], _portfolio(), {"STOCK": 1.0}, WEIGHTS, strategy="equilibrado")[0]
    assert not any("elegível" in f.lower() for f in r.red_flags)


# --- Fase 2: calibrações do método ---

def test_besst_affinity_is_graded():
    from app.services.scoring import _besst_affinity
    assert _besst_affinity("Bancos") == 1.0
    assert _besst_affinity("Energia Elétrica") == 1.0
    assert _besst_affinity("Serviços Financeiros") == 0.3  # corretora/fintech não é "banco" de Barsi
    assert _besst_affinity("Mineração") == 0.0             # setor presente, sem afinidade
    assert _besst_affinity(None) is None                    # setor ausente


def test_bazin_ceiling_price_exposed_and_below_flag():
    a = Asset(ticker="C3", asset_class="STOCK", sector="Energia", price=20.0,
              fundamentals=Fundamentals(pvp=1.0, pl=8.0),
              dividends_by_year={"2022": 2.0, "2023": 2.0, "2024": 2.0})
    s = score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS)[0]
    assert s.bazin_ceiling_price is not None and abs(s.bazin_ceiling_price - 33.33) < 0.1
    assert s.bazin_below_ceiling is True  # preço 20 < teto 33,3


def test_bazin_target_yield_configurable():
    a = Asset(ticker="C3", asset_class="STOCK", sector="Energia", price=20.0,
              fundamentals=Fundamentals(pvp=1.0, pl=8.0),
              dividends_by_year={"2022": 2.0, "2023": 2.0, "2024": 2.0})
    s = score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS, bazin_target_yield=0.08)[0]
    assert abs(s.bazin_ceiling_price - 25.0) < 0.1  # 2,0 / 0,08 = 25


def test_resolve_bazin_target_yield():
    from app.services.scoring import resolve_bazin_target_yield
    assert resolve_bazin_target_yield("fixed_6", 0.06, None) == 0.06
    assert resolve_bazin_target_yield("fixed_6", 0.08, 0.14) == 0.08          # manual ignora CDI
    assert resolve_bazin_target_yield("dynamic_selic", 0.06, 0.14) == 0.07    # max(0,06; 0,5×0,14)
    assert resolve_bazin_target_yield("dynamic_selic", 0.06, None) == 0.06    # sem CDI → manual


def test_sector_normalization_groups_by_sector_with_fallback():
    banks = [
        Asset(ticker=f"BANK{i}", asset_class="STOCK", sector="Bancos", price=10.0,
              fundamentals=Fundamentals(pvp=pvp, pl=6.0))
        for i, pvp in enumerate([0.6, 0.8, 1.0, 1.2])  # 4 bancos => normaliza por setor
    ]
    miner = Asset(ticker="MINE3", asset_class="STOCK", sector="Mineração", price=10.0,
                  fundamentals=Fundamentals(pvp=0.5, pl=6.0))
    r = score_assets(banks + [miner], _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    bank0 = next(x for x in r if x.ticker == "BANK0")
    assert next(m for m in bank0.metrics if m.key == "pvp").peer_group == "Bancos"
    mine = next(x for x in r if x.ticker == "MINE3")
    assert next(m for m in mine.metrics if m.key == "pvp").peer_group == "STOCK"  # setor raro → classe


def test_fii_payout_not_penalized():
    fii = Asset(ticker="XPLG11", asset_class="FII", sector="Imobiliário", price=100.0,
                fundamentals=Fundamentals(pvp=1.0, lpa=8.0),
                dividends_by_year={"2022": 9.0, "2023": 9.0, "2024": 9.0})  # payout >100%
    r = score_assets([fii], _portfolio(), {"FII": 1.0}, WEIGHTS)[0]
    assert not any("ayout" in f for f in r.red_flags)  # FII distribui ~100% por lei: isento


def test_consistency_weighted_at_least_as_much_as_yield():
    a = Asset(ticker="D3", asset_class="STOCK", sector="Bancos", price=20.0,
              fundamentals=Fundamentals(pvp=0.9, pl=7.0, dividend_yield=0.08),
              dividends_by_year={"2021": 2.0, "2022": 2.0, "2023": 2.0, "2024": 2.0})
    by = {m.key: m for m in score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS)[0].metrics}
    assert by["dividend_consistency"].weight >= by["div_yield"].weight
    assert by["dividend_consistency"].weight >= by["bazin_ceiling"].weight


def test_barsi_filter_excludes_low_liquidity():
    a = Asset(ticker="ILLIQ3", asset_class="STOCK", sector="Bancos", price=20.0,
              fundamentals=Fundamentals(pvp=0.8, pl=6.0, dividend_yield=0.08,
                                        avg_daily_liquidity=2_000_000.0),  # < R$ 5 mi
              dividends_by_year={"2022": 1.6, "2023": 1.7, "2024": 1.8})
    r = score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS, strategy="barsi")[0]
    assert r.composite_score == 0.0
    assert any("Liquidez" in f for f in r.red_flags)
