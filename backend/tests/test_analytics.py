"""Testes de renda passiva: renda atual, bola de neve e aporte necessário."""
from __future__ import annotations

from app.models.portfolio import Position
from app.services import analytics


def _pos(ticker, value):
    return Position(ticker=ticker, value=value, weight=0.0)


def test_portfolio_income_sums_value_times_dy():
    positions = [_pos("BBAS3", 10000.0), _pos("XPLG11", 5000.0), _pos("NODIV3", 2000.0)]
    dy = {"BBAS3": 0.10, "XPLG11": 0.08, "NODIV3": None}
    r = analytics.portfolio_income(positions, dy)
    assert r["annual_income"] == 1400.0  # 1000 + 400 + 0
    assert r["monthly_income"] == round(1400 / 12, 2)
    assert r["total_value"] == 17000.0
    # portfolio_yield = 1400/17000
    assert abs(r["portfolio_yield"] - 1400 / 17000) < 1e-4
    assert [a["ticker"] for a in r["by_asset"]] == ["BBAS3", "XPLG11"]  # ordenado por renda, sem o sem-DY


def test_snowball_no_growth_no_reinvest_is_linear_contributions():
    # sem reinvestir e sem crescimento: patrimônio = aporte acumulado + valor inicial
    r = analytics.snowball(0.0, 100.0, 0.06, 0.0, years=1, reinvest=False)
    assert r["series"][-1]["invested"] == 1200.0
    assert r["series"][-1]["value"] == 1200.0  # nada reinvestido


def test_snowball_reinvest_beats_no_reinvest():
    a = analytics.snowball(10000.0, 500.0, 0.09, 0.0, years=20, reinvest=True)
    b = analytics.snowball(10000.0, 500.0, 0.09, 0.0, years=20, reinvest=False)
    assert a["final_value"] > b["final_value"]
    assert a["final_monthly_income"] > b["final_monthly_income"]
    assert len(a["series"]) == 20


def test_required_contribution_reaches_target():
    target = 5000.0  # R$/mês em 20 anos
    contrib = analytics.required_monthly_contribution(target, 0.0, 0.08, 0.0, years=20)
    assert contrib is not None and contrib > 0
    # aportando o valor calculado, a renda final deve alcançar ~o alvo
    final = analytics.snowball(0.0, contrib, 0.08, 0.0, years=20)["final_monthly_income"]
    assert final >= target * 0.98


def test_required_contribution_zero_when_already_there():
    # carteira que já gera a renda-alvo sem aportes
    contrib = analytics.required_monthly_contribution(100.0, 1_000_000.0, 0.08, 0.0, years=10)
    assert contrib == 0.0
