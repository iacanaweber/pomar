"""Calendário de proventos — projeta a renda mês a mês da carteira atual (lógica pura).

Usa a sazonalidade média (provento médio por mês por cota, dos últimos anos) × quantidade de
cotas de cada posição. É uma ESTIMATIVA sazonal (não datas futuras garantidas).
"""
from __future__ import annotations

from typing import Dict, List

from app.models.portfolio import Position


def project_calendar(
    positions: List[Position], seasonality_by_ticker: Dict[str, Dict[int, float]]
) -> dict:
    months: Dict[int, float] = {m: 0.0 for m in range(1, 13)}
    by_asset: Dict[int, List[dict]] = {m: [] for m in range(1, 13)}
    for p in positions:
        season = seasonality_by_ticker.get(p.ticker) or {}
        qty = p.quantity or 0
        if not season or not qty:
            continue
        for m in range(1, 13):
            val = float(season.get(m, 0.0)) * float(qty)
            if val > 0:
                months[m] += val
                by_asset[m].append({"ticker": p.ticker, "income": round(val, 2)})
    month_list = []
    for m in range(1, 13):
        ranked = sorted(by_asset[m], key=lambda x: x["income"], reverse=True)
        month_list.append({"month": m, "income": round(months[m], 2), "by_asset": ranked})
    return {"months": month_list, "annual_total": round(sum(months.values()), 2)}
