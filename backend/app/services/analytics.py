"""Analytics de renda passiva — renda atual estimada da carteira.

Função pura (testável) separada da orquestração de I/O: Σ valor×DY das posições, com
Yield on Cost quando o Ghostfolio informa o custo.
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
