"""Testes da projeção do calendário de proventos (puro)."""
from __future__ import annotations

from app.models.portfolio import Position
from app.services.calendar import project_calendar


def test_project_calendar_distributes_by_month():
    positions = [Position(ticker="X3", asset_class="STOCK", value=1000.0, weight=1.0, quantity=100)]
    season = {"X3": {6: 0.5, 12: 0.8}}  # paga ~R$0,50/cota em jun e R$0,80 em dez
    out = project_calendar(positions, season)
    months = {m["month"]: m["income"] for m in out["months"]}
    assert months[6] == 50.0   # 0,5 × 100 cotas
    assert months[12] == 80.0  # 0,8 × 100
    assert months[1] == 0.0
    assert out["annual_total"] == 130.0
    assert len(out["months"]) == 12


def test_project_calendar_skips_positions_without_data():
    positions = [Position(ticker="Y3", asset_class="STOCK", value=1000.0, weight=1.0, quantity=None)]
    out = project_calendar(positions, {"Y3": {6: 1.0}})
    assert out["annual_total"] == 0.0  # sem quantidade -> não projeta
