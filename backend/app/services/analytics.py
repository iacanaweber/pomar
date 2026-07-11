"""Analytics de renda passiva — renda atual da carteira e projeção "bola de neve".

Funções puras (testáveis) separadas da orquestração de I/O. A renda atual é Σ valor×DY
das posições; a projeção simula mês a mês aporte + dividendos (com reinvestimento opcional
e crescimento anual dos proventos).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.models.portfolio import Position


def portfolio_income(positions: List[Position], dy_by_ticker: Dict[str, Optional[float]]) -> dict:
    """Renda anual/mensal estimada a partir do DY de cada posição (valor × DY).

    Quando há preço médio/custo (Ghostfolio), também calcula o Yield on Cost (renda ÷ custo).
    """
    by_asset: List[dict] = []
    annual = 0.0
    total_value = 0.0
    income_with_cost = 0.0
    cost_with_income = 0.0
    for p in positions:
        total_value += p.value
        dy = dy_by_ticker.get(p.ticker)
        if dy and dy > 0:
            inc = p.value * dy
            annual += inc
            cost = getattr(p, "cost_basis", None)
            yoc = round(inc / cost, 4) if (cost and cost > 0) else None
            if cost and cost > 0:
                income_with_cost += inc
                cost_with_income += cost
            by_asset.append(
                {
                    "ticker": p.ticker,
                    "name": p.name,
                    "value": round(p.value, 2),
                    "dividend_yield": round(dy, 4),
                    "annual_income": round(inc, 2),
                    "cost_basis": round(cost, 2) if cost else None,
                    "yield_on_cost": yoc,
                }
            )
    by_asset.sort(key=lambda x: x["annual_income"], reverse=True)
    return {
        "annual_income": round(annual, 2),
        "monthly_income": round(annual / 12, 2),
        "portfolio_yield": round(annual / total_value, 4) if total_value > 0 else 0.0,
        "yield_on_cost": round(income_with_cost / cost_with_income, 4) if cost_with_income > 0 else None,
        "total_value": round(total_value, 2),
        "by_asset": by_asset,
    }


def snowball(
    current_value: float,
    monthly_contribution: float,
    annual_yield: float,
    annual_growth: float = 0.0,
    years: int = 20,
    reinvest: bool = True,
    annual_inflation: float = 0.0,
) -> dict:
    """Simula a bola de neve de dividendos mês a mês.

    Modelo (v4): o DY é CONSTANTE ao longo da simulação — quando os proventos de uma
    empresa crescem, o preço tende a acompanhar e o yield fica ~estável. Por isso
    `annual_growth` aplica-se ao PATRIMÔNIO (valorização de preço que acompanha o
    crescimento dos proventos), não ao yield. (O modelo anterior expandia o yield
    perpetuamente — 8% virava 21% em 20 anos — sobre um patrimônio parado, inflando a
    renda projetada em até ~3×.)

    Taxas mensais equivalentes ((1+a)^(1/12)−1) evitam o viés de compor a/12.
    `annual_inflation` deflaciona a renda para reais DE HOJE (campos *_real) — a meta
    do usuário é digitada em reais de hoje, então é contra o real que se compara.

    A cada mês: recebe dividendos (yield mensal do patrimônio), o patrimônio valoriza
    pelo growth mensal, entra o aporte e, se `reinvest`, os dividendos voltam ao bolo.
    `annual_income` da série = dividendos efetivamente creditados no ano (não o
    patrimônio de dezembro × yield, que superestimava).
    """
    years = max(1, min(years, 80))
    m_yield = (1 + annual_yield) ** (1 / 12) - 1 if annual_yield > 0 else 0.0
    m_growth = (1 + max(annual_growth, -0.9)) ** (1 / 12) - 1
    value = current_value
    total_invested = current_value
    total_dividends = 0.0
    year_dividends = 0.0
    series: List[dict] = []
    for m in range(1, years * 12 + 1):
        income = value * m_yield
        total_dividends += income
        year_dividends += income
        value *= 1 + m_growth
        value += monthly_contribution
        total_invested += monthly_contribution
        if reinvest:
            value += income
        if m % 12 == 0:
            y = m // 12
            deflator = (1 + annual_inflation) ** y
            run_rate = value * annual_yield / 12  # renda mensal ao ritmo do fim do ano
            series.append(
                {
                    "year": y,
                    "value": round(value, 2),
                    "invested": round(total_invested, 2),
                    "annual_income": round(year_dividends, 2),
                    "monthly_income": round(run_rate, 2),
                    "monthly_income_real": round(run_rate / deflator, 2),
                }
            )
            year_dividends = 0.0
    final = series[-1] if series else {}
    return {
        "series": series,
        "final_value": final.get("value", round(value, 2)),
        "final_monthly_income": final.get("monthly_income", 0.0),
        "final_monthly_income_real": final.get("monthly_income_real", 0.0),
        "total_invested": round(total_invested, 2),
        "total_dividends": round(total_dividends, 2),
    }


def required_monthly_contribution(
    target_monthly_income: float,
    current_value: float,
    annual_yield: float,
    annual_growth: float = 0.0,
    years: int = 20,
    reinvest: bool = True,
    annual_inflation: float = 0.0,
) -> Optional[float]:
    """Quanto aportar por mês para atingir uma renda mensal-alvo em `years` (busca binária).

    A meta é em reais de hoje, então a comparação usa a renda DEFLACIONADA.
    Sem yield não há renda de dividendos: retorna None (impossível), não R$ 0.
    """
    if target_monthly_income <= 0:
        return 0.0
    if annual_yield <= 0:
        return None

    def income_at(contrib: float) -> float:
        return snowball(
            current_value, contrib, annual_yield, annual_growth, years, reinvest, annual_inflation
        )["final_monthly_income_real"]

    if income_at(0.0) >= target_monthly_income:
        return 0.0  # a carteira atual já chega lá
    lo, hi = 0.0, 1000.0
    # expande o teto até cobrir o alvo (com limite de segurança)
    while income_at(hi) < target_monthly_income and hi < 1e9:
        hi *= 2
    if income_at(hi) < target_monthly_income:
        return None
    for _ in range(60):  # converge ao centavo
        mid = (lo + hi) / 2
        if income_at(mid) >= target_monthly_income:
            hi = mid
        else:
            lo = mid
    return round(hi, 2)


def estimated_years_to_goal(
    target_monthly_income: float,
    current_value: float,
    monthly_contribution: float,
    annual_yield: float,
    annual_growth: float = 0.0,
    reinvest: bool = True,
    max_years: int = 80,
    annual_inflation: float = 0.0,
) -> Optional[int]:
    """Menor nº de anos para a renda mensal (em reais de hoje) atingir a meta. None se nunca."""
    if target_monthly_income <= 0 or annual_yield <= 0:
        return None
    sb = snowball(
        current_value, monthly_contribution, annual_yield, annual_growth,
        max_years, reinvest, annual_inflation,
    )
    for point in sb["series"]:
        if point["monthly_income_real"] >= target_monthly_income:
            return point["year"]
    return None
