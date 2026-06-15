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
    # dividendo médio 2.0; preço-teto = 2/0.06 = 33.3; preço 20 => margem positiva
    a = Asset(ticker="TEST3", asset_class="STOCK", sector="Energia", price=20.0,
              fundamentals=Fundamentals(pvp=1.0, pl=8.0, dividend_yield=0.10),
              dividends_by_year={"2023": 2.0, "2024": 2.0})
    ranking = score_assets([a], _portfolio(), {"STOCK": 1.0}, WEIGHTS)
    bazin = next(m for m in ranking[0].metrics if m.key == "bazin_ceiling")
    assert bazin.raw_value is not None and bazin.raw_value > 0
