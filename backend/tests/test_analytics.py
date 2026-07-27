"""Testes de renda passiva: renda atual estimada da carteira e Yield on Cost."""
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


def test_portfolio_income_yield_on_cost():
    positions = [Position(ticker="BBAS3", asset_class="STOCK", value=10_000.0, weight=1.0,
                          cost_basis=8_000.0)]
    out = analytics.portfolio_income(positions, {"BBAS3": 0.10})
    a = out["by_asset"][0]
    assert a["annual_income"] == 1000.0
    assert a["yield_on_cost"] == 0.125    # 1000 / 8000
    assert out["yield_on_cost"] == 0.125  # agregado


def test_yield_on_cost_none_without_cost():
    out = analytics.portfolio_income(
        [Position(ticker="X3", asset_class="STOCK", value=1000.0, weight=1.0)], {"X3": 0.08}
    )
    assert out["by_asset"][0]["yield_on_cost"] is None
    assert out["yield_on_cost"] is None
