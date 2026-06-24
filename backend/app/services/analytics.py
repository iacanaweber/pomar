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
) -> dict:
    """Simula a bola de neve de dividendos mês a mês.

    A cada mês: recebe dividendos (yield/12 do patrimônio), aporta o valor mensal e, se
    `reinvest`, soma os dividendos ao patrimônio. O yield cresce `annual_growth` ao ano.
    Retorna a série anual e o resumo final.
    """
    years = max(1, min(years, 80))
    value = current_value
    total_invested = current_value
    total_dividends = 0.0
    series: List[dict] = []
    for m in range(1, years * 12 + 1):
        cur_yield = annual_yield * ((1 + annual_growth) ** ((m - 1) // 12))
        income = value * (cur_yield / 12)
        total_dividends += income
        value += monthly_contribution
        total_invested += monthly_contribution
        if reinvest:
            value += income
        if m % 12 == 0:
            series.append(
                {
                    "year": m // 12,
                    "value": round(value, 2),
                    "invested": round(total_invested, 2),
                    "annual_income": round(value * cur_yield, 2),
                    "monthly_income": round(value * cur_yield / 12, 2),
                }
            )
    final = series[-1] if series else {}
    return {
        "series": series,
        "final_value": final.get("value", round(value, 2)),
        "final_monthly_income": final.get("monthly_income", 0.0),
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
) -> Optional[float]:
    """Quanto aportar por mês para atingir uma renda mensal-alvo em `years` (busca binária)."""
    if target_monthly_income <= 0 or annual_yield <= 0:
        return 0.0

    def income_at(contrib: float) -> float:
        return snowball(current_value, contrib, annual_yield, annual_growth, years, reinvest)[
            "final_monthly_income"
        ]

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
) -> Optional[int]:
    """Menor nº de anos para a renda mensal atingir a meta, com o aporte atual. None se nunca."""
    if target_monthly_income <= 0 or annual_yield <= 0:
        return None
    for y in range(1, max_years + 1):
        sb = snowball(current_value, monthly_contribution, annual_yield, annual_growth, y, reinvest)
        if sb["final_monthly_income"] >= target_monthly_income:
            return y
    return None
