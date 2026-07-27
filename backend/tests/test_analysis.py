"""Testes da leitura factual do ativo: preço-teto de Bazin, proventos e red flags."""
from __future__ import annotations

from app.models.market import Asset, Fundamentals
from app.services.analysis import (
    _dividend_cagr,
    _dividend_consistency,
    analyze_asset,
    resolve_bazin_target_yield,
)


# --- preço-teto de Bazin ---

def test_bazin_ceiling_and_below_flag():
    # dividendo médio 2,0 => teto = 2/0,06 = 33,33; preço 20 => abaixo do teto
    a = Asset(ticker="C3", asset_class="STOCK", sector="Energia", price=20.0,
              fundamentals=Fundamentals(pvp=1.0, pl=8.0),
              dividends_by_year={"2022": 2.0, "2023": 2.0, "2024": 2.0})
    an = analyze_asset(a)
    assert an.bazin_ceiling_price is not None and abs(an.bazin_ceiling_price - 33.33) < 0.1
    assert an.bazin_below_ceiling is True
    assert an.bazin_margin is not None and an.bazin_margin > 0


def test_bazin_unavailable_without_min_paid_years():
    # só 2 anos pagos => indisponível (não derivar teto de média curta)
    a = Asset(ticker="C3", asset_class="STOCK", price=20.0,
              dividends_by_year={"2023": 2.0, "2024": 2.0})
    an = analyze_asset(a)
    assert an.bazin_ceiling_price is None
    assert an.bazin_below_ceiling is None
    assert an.bazin_margin is None


def test_bazin_mean_conta_anos_sem_pagamento():
    """Ano sem pagar REDUZ o teto (média pela janela completa) — pagadora irregular não
    ganha teto de pagadora perene."""
    paid_only = Asset(ticker="AAA3", asset_class="STOCK", price=20.0,
                      dividends_by_year={"2022": 2.0, "2023": 2.0, "2024": 2.0})
    with_zero = Asset(ticker="BBB3", asset_class="STOCK", price=20.0,
                      dividends_by_year={"2021": 2.0, "2022": 0.0, "2023": 2.0, "2024": 2.0})
    a = analyze_asset(paid_only)
    b = analyze_asset(with_zero)
    assert abs(a.bazin_ceiling_price - 33.33) < 0.01  # média 2,0
    assert abs(b.bazin_ceiling_price - 25.0) < 0.01   # média (2+0+2+2)/4 = 1,5
    assert a.bazin_margin > b.bazin_margin


def test_bazin_target_yield_configurable():
    a = Asset(ticker="C3", asset_class="STOCK", price=20.0,
              dividends_by_year={"2022": 2.0, "2023": 2.0, "2024": 2.0})
    an = analyze_asset(a, bazin_target_yield=0.08)
    assert abs(an.bazin_ceiling_price - 25.0) < 0.1  # 2,0 / 0,08
    assert an.bazin_target_yield == 0.08


def test_resolve_bazin_target_yield():
    assert resolve_bazin_target_yield("fixed_6", 0.06, None) == 0.06
    assert resolve_bazin_target_yield("fixed_6", 0.08, 0.14) == 0.08          # manual ignora CDI
    assert resolve_bazin_target_yield("dynamic_selic", 0.06, 0.14) == 0.07    # max(0,06; 0,5×0,14)
    assert resolve_bazin_target_yield("dynamic_selic", 0.06, None) == 0.06    # sem CDI → manual


# --- proventos ---

def test_consistencia_penaliza_corte_forte():
    """Corte >50% a/a reduz a consistência — presença não é perenidade."""
    estavel = Asset(ticker="EST3", asset_class="STOCK",
                    dividends_by_year={"2022": 2.0, "2023": 2.0, "2024": 2.0})
    cortou = Asset(ticker="CUT3", asset_class="STOCK",
                   dividends_by_year={"2022": 2.0, "2023": 0.2, "2024": 0.2})
    assert _dividend_consistency(estavel) == 1.0
    c = _dividend_consistency(cortou)
    assert c is not None and c < 0.8


def test_dividend_cagr():
    crescendo = Asset(ticker="GROW3", asset_class="STOCK", price=20.0,
                      dividends_by_year={"2020": 1.0, "2021": 1.2, "2022": 1.4,
                                         "2023": 1.6, "2024": 1.8})
    caindo = Asset(ticker="FALL3", asset_class="STOCK", price=20.0,
                   dividends_by_year={"2020": 2.0, "2021": 1.6, "2022": 1.2,
                                      "2023": 0.8, "2024": 0.4})
    g_up = _dividend_cagr(crescendo)
    g_down = _dividend_cagr(caindo)
    assert g_up is not None and g_up > 0.10
    assert g_down is not None and g_down < 0.0
    # histórico curto ou base zero: indisponível, nunca inventado
    curto = Asset(ticker="NEW3", asset_class="STOCK", price=10.0,
                  dividends_by_year={"2023": 1.0, "2024": 1.1})
    assert _dividend_cagr(curto) is None


# --- red flags e selo de risco (anti value-trap) ---

def test_loss_making_gets_red_flag():
    a = Asset(ticker="LOSS3", asset_class="STOCK", price=10.0,
              fundamentals=Fundamentals(pvp=0.5, pl=-5.0, dividend_yield=0.15))
    an = analyze_asset(a)
    assert any("prejuízo" in f.lower() for f in an.red_flags)
    assert an.risk_level == "vermelho"


def test_high_debt_flags():
    levered = Asset(ticker="DEBT3", asset_class="STOCK", price=10.0,
                    fundamentals=Fundamentals(pvp=1.0, pl=8.0, dividend_yield=0.08,
                                              net_debt_to_ebitda=6.0))
    an = analyze_asset(levered)
    assert any("ndividamento" in f for f in an.red_flags)


def test_payout_over_100_flags():
    a = Asset(ticker="PAY3", asset_class="STOCK", price=10.0,
              fundamentals=Fundamentals(pvp=1.0, pl=8.0, lpa=1.0),
              dividends_by_year={"2022": 1.5, "2023": 1.5, "2024": 1.5})
    an = analyze_asset(a)
    assert any("ayout" in f for f in an.red_flags)
    assert an.payout_ratio is not None and an.payout_ratio > 1.0


def test_fii_payout_not_penalized():
    fii = Asset(ticker="XPLG11", asset_class="FII", sector="Imobiliário", price=100.0,
                fundamentals=Fundamentals(pvp=1.0, lpa=8.0),
                dividends_by_year={"2022": 9.0, "2023": 9.0, "2024": 9.0})  # payout >100%
    an = analyze_asset(fii)
    assert not any("ayout" in f for f in an.red_flags)  # FII distribui ~100% por lei


def test_above_ceiling_is_a_flag():
    caro = Asset(ticker="CAR3", asset_class="STOCK", price=100.0,
                 fundamentals=Fundamentals(pvp=1.0, pl=8.0),
                 dividends_by_year={"2022": 2.0, "2023": 2.0, "2024": 2.0})  # teto 33,33
    an = analyze_asset(caro)
    assert an.bazin_below_ceiling is False
    assert any("acima do preço-teto" in f for f in an.red_flags)


def test_healthy_asset_is_green_with_highlights():
    a = Asset(ticker="GOOD3", asset_class="STOCK", sector="Bancos", price=20.0,
              fundamentals=Fundamentals(pvp=0.8, pl=6.0, dividend_yield=0.09, lpa=3.0, vpa=25.0,
                                        net_debt_to_ebitda=1.0, roe=0.18),
              dividends_by_year={"2022": 2.0, "2023": 2.1, "2024": 2.2})
    an = analyze_asset(a)
    assert an.risk_level == "verde"
    assert an.red_flags == []
    assert any("preço-teto" in h for h in an.highlights)
    assert any("consistente" in h for h in an.highlights)
    assert any("ROE" in h for h in an.highlights)


def test_low_liquidity_flags():
    a = Asset(ticker="ILLIQ3", asset_class="STOCK", price=20.0,
              fundamentals=Fundamentals(pvp=0.8, pl=6.0, avg_daily_liquidity=100_000.0))
    an = analyze_asset(a)
    assert any("Liquidez" in f for f in an.red_flags)


def test_missing_data_is_neutral():
    """Fonte ausente não é motivo ruim: sem fundamentos, nada de red flag inventada."""
    a = Asset(ticker="VAZIO3", asset_class="STOCK", price=10.0)
    an = analyze_asset(a)
    assert an.red_flags == []
    assert an.risk_level == "verde"
    assert an.dividend_consistency is None and an.payout_ratio is None
