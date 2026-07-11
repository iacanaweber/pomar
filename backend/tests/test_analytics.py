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


# --- v4: modelo corrigido da bola de neve ---

def test_snowball_growth_nao_expande_o_yield():
    """Cenário do achado crítico da auditoria: 100k + R$1.000/mês, DY 8%, growth 5%,
    20 anos. O modelo antigo projetava ~R$47 mil/mês (yield expandindo até 21% sobre
    patrimônio parado); o corrigido mantém DY constante e growth no patrimônio."""
    r = analytics.snowball(100_000.0, 1000.0, 0.08, 0.05, years=20)
    assert r["final_monthly_income"] < 25_000.0  # o modelo antigo dava ~47.080
    # coerência interna: renda final = patrimônio final × DY/12 (yield NÃO expandiu)
    assert abs(r["final_monthly_income"] - r["final_value"] * 0.08 / 12) < 1.0


def test_snowball_growth_positivo_aumenta_patrimonio():
    base = analytics.snowball(100_000.0, 1000.0, 0.08, 0.0, years=20)
    up = analytics.snowball(100_000.0, 1000.0, 0.08, 0.05, years=20)
    down = analytics.snowball(100_000.0, 1000.0, 0.08, -0.05, years=20)
    assert up["final_value"] > base["final_value"] > down["final_value"]


def test_snowball_inflacao_deflaciona_para_reais_de_hoje():
    r = analytics.snowball(100_000.0, 1000.0, 0.08, 0.0, years=20, annual_inflation=0.04)
    nominal = r["final_monthly_income"]
    real = r["final_monthly_income_real"]
    assert abs(real - nominal / (1.04 ** 20)) < 1.0
    # sem inflação, real == nominal
    r0 = analytics.snowball(100_000.0, 1000.0, 0.08, 0.0, years=20)
    assert r0["final_monthly_income_real"] == r0["final_monthly_income"]


def test_snowball_annual_income_e_o_creditado_no_ano():
    """annual_income da série = dividendos do ano, não patrimônio de dezembro × yield."""
    r = analytics.snowball(120_000.0, 0.0, 0.06, 0.0, years=1, reinvest=False)
    p = r["series"][0]
    # 12 meses de ~120k × taxa mensal equivalente ≈ 6% a.a. sobre 120k (patrimônio parado)
    assert abs(p["annual_income"] - 120_000.0 * 0.06) < 120_000.0 * 0.06 * 0.03
    # e é menor que o cálculo antigo (patrimônio final × yield) quando há aporte
    r2 = analytics.snowball(0.0, 1000.0, 0.08, 0.0, years=1)
    assert r2["series"][0]["annual_income"] < r2["series"][0]["value"] * 0.08


def test_required_contribution_none_sem_yield():
    """DY 0 e meta > 0: impossível (None), não 'R$ 0,00/mês'."""
    assert analytics.required_monthly_contribution(5000.0, 100_000.0, 0.0, 0.0, years=20) is None


def test_required_contribution_considera_inflacao():
    sem = analytics.required_monthly_contribution(3000.0, 0.0, 0.08, 0.0, years=20)
    com = analytics.required_monthly_contribution(
        3000.0, 0.0, 0.08, 0.0, years=20, annual_inflation=0.04
    )
    assert sem is not None and com is not None and com > sem  # meta real exige aportar mais


# --- Fase 3: Yield on Cost e anos até a meta ---

def test_portfolio_income_yield_on_cost():
    from app.models.portfolio import Position

    positions = [Position(ticker="BBAS3", asset_class="STOCK", value=10_000.0, weight=1.0,
                          cost_basis=8_000.0)]
    out = analytics.portfolio_income(positions, {"BBAS3": 0.10})
    a = out["by_asset"][0]
    assert a["annual_income"] == 1000.0
    assert a["yield_on_cost"] == 0.125    # 1000 / 8000
    assert out["yield_on_cost"] == 0.125  # agregado


def test_yield_on_cost_none_without_cost():
    from app.models.portfolio import Position

    out = analytics.portfolio_income(
        [Position(ticker="X3", asset_class="STOCK", value=1000.0, weight=1.0)], {"X3": 0.08}
    )
    assert out["by_asset"][0]["yield_on_cost"] is None
    assert out["yield_on_cost"] is None


def test_estimated_years_to_goal_monotonic():
    y_small = analytics.estimated_years_to_goal(5000.0, 0.0, 1000.0, 0.08)
    y_big = analytics.estimated_years_to_goal(5000.0, 0.0, 3000.0, 0.08)
    assert y_small is not None and y_big is not None
    assert y_big <= y_small  # aporte maior chega antes
