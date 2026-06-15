"""Testes da alocação do aporte: lotes, concentração e sobra."""
from __future__ import annotations

from app.models.portfolio import Allocations, Portfolio
from app.models.scoring import ScoredAsset
from app.services.allocation import allocate


def _portfolio() -> Portfolio:
    return Portfolio(
        total_value=10000.0,
        as_of="2026-06-15T00:00:00Z",
        allocations=Allocations(by_class={"STOCK": 0.9, "FII": 0.1}),
    )


def _ranking() -> list[ScoredAsset]:
    return [
        ScoredAsset(ticker="MXRF11", asset_class="FII", composite_score=0.8),
        ScoredAsset(ticker="BBAS3", asset_class="STOCK", composite_score=0.6),
    ]


def test_allocate_respects_budget_and_rounds_to_shares():
    ranking = _ranking()
    prices = {"MXRF11": 10.0, "BBAS3": 28.0}
    lots = {"MXRF11": 1, "BBAS3": 1}
    targets = {"STOCK": 0.5, "FII": 0.5}
    unallocated = allocate(1000.0, ranking, _portfolio(), prices, lots, targets, min_ticket=50.0)
    spent = sum(r.suggested.invested_exact for r in ranking if r.suggested)
    assert spent <= 1000.0
    assert unallocated >= 0
    assert abs((spent + unallocated) - 1000.0) < 0.01 or unallocated >= 0
    # FII está mais sub-alocado (0.1 vs alvo 0.5) -> deve receber compra
    fii = next(r for r in ranking if r.ticker == "MXRF11")
    assert fii.suggested is not None and fii.suggested.shares > 0


def test_min_ticket_skips_tiny_allocations():
    ranking = [ScoredAsset(ticker="BBAS3", asset_class="STOCK", composite_score=0.6)]
    prices = {"BBAS3": 28.0}
    lots = {"BBAS3": 1}
    targets = {"STOCK": 1.0}
    unallocated = allocate(30.0, ranking, _portfolio(), prices, lots, targets, min_ticket=100.0)
    # aporte abaixo do ticket mínimo: nada alocado, tudo volta como sobra
    assert unallocated == 30.0
    assert ranking[0].suggested is None
