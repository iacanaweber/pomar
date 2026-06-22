"""Testes da alocação do aporte (v2): need-based, slots por classe, 2ª passada, conservação."""
from __future__ import annotations

from app.models.portfolio import Allocations, Portfolio
from app.models.scoring import ScoredAsset
from app.services.allocation import allocate


def _portfolio(by_class=None, total=10000.0) -> Portfolio:
    return Portfolio(
        total_value=total,
        as_of="2026-06-15T00:00:00Z",
        allocations=Allocations(by_class=by_class or {"STOCK": 0.9, "FII": 0.1}),
    )


def _ranking() -> list[ScoredAsset]:
    return [
        ScoredAsset(ticker="MXRF11", asset_class="FII", composite_score=0.8),
        ScoredAsset(ticker="BBAS3", asset_class="STOCK", composite_score=0.6),
    ]


def test_allocate_conserves_money_and_rounds_to_shares():
    ranking = _ranking()
    prices = {"MXRF11": 10.0, "BBAS3": 28.0}
    lots = {"MXRF11": 1, "BBAS3": 1}
    targets = {"STOCK": 0.5, "FII": 0.5}
    unallocated = allocate(1000.0, ranking, _portfolio(), prices, lots, targets, min_ticket=50.0)
    spent = sum(r.suggested.invested_exact for r in ranking if r.suggested)
    # conservação dura (não-tautológica): gasto + sobra == aporte
    assert abs((spent + unallocated) - 1000.0) < 0.05
    assert spent <= 1000.0 + 1e-6 and unallocated >= 0
    # FII está mais sub-alocado (0.1 vs alvo 0.5) -> deve receber compra
    fii = next(r for r in ranking if r.ticker == "MXRF11")
    assert fii.suggested is not None and fii.suggested.shares > 0


def test_min_ticket_skips_tiny_allocations():
    ranking = [ScoredAsset(ticker="BBAS3", asset_class="STOCK", composite_score=0.6)]
    prices = {"BBAS3": 28.0}
    lots = {"BBAS3": 1}
    targets = {"STOCK": 1.0}
    unallocated = allocate(30.0, ranking, _portfolio(), prices, lots, targets, min_ticket=100.0)
    # aporte abaixo do ticket mínimo: nada alocado (a 2ª passada não abre posição abaixo do piso)
    assert unallocated == 30.0
    assert ranking[0].suggested is None


def test_need_based_avoids_overcorrection():
    # Caso do ANALISE-V2: carteira 1000 (STOCK 90/FII 10), aporte 1000, alvos 50/50.
    # need STOCK=100, FII=900 -> resultado fica ~50/50 (sem jogar o FII acima do alvo).
    ranking = [
        ScoredAsset(ticker="FXXX11", asset_class="FII", composite_score=0.7),
        ScoredAsset(ticker="SXXX3", asset_class="STOCK", composite_score=0.7),
    ]
    prices = {"FXXX11": 10.0, "SXXX3": 10.0}
    lots = {"FXXX11": 1, "SXXX3": 1}
    targets = {"STOCK": 0.5, "FII": 0.5}
    pf = _portfolio(by_class={"STOCK": 0.9, "FII": 0.1}, total=1000.0)
    allocate(1000.0, ranking, pf, prices, lots, targets, max_weight_per_asset=1.0, min_ticket=10.0)
    fii = next(r for r in ranking if r.ticker == "FXXX11").suggested
    stock = next(r for r in ranking if r.ticker == "SXXX3").suggested
    assert fii and stock
    # FII (mais sub-alocado) recebe muito mais que STOCK
    assert fii.invested_exact > stock.invested_exact
    # STOCK recebe ~100 e FII ~900 (need-based), não 500/500
    assert 80 <= stock.invested_exact <= 160
    assert 840 <= fii.invested_exact <= 920


def test_slots_distributed_so_suballocated_class_is_bought():
    # 6 STOCK + 1 FII, max_assets=5; ambas as classes com need -> o FII NÃO pode ser
    # esganado pela 1a classe (corrige o viés do contador global).
    ranking = [ScoredAsset(ticker=f"ST{i}3", asset_class="STOCK", composite_score=0.9 - i * 0.05) for i in range(6)]
    ranking.append(ScoredAsset(ticker="FII11", asset_class="FII", composite_score=0.5))
    prices = {r.ticker: 10.0 for r in ranking}
    lots = {r.ticker: 1 for r in ranking}
    targets = {"STOCK": 0.5, "FII": 0.5}
    pf = _portfolio(by_class={"STOCK": 0.5, "FII": 0.5}, total=1000.0)
    allocate(1000.0, ranking, pf, prices, lots, targets, max_assets=5, max_weight_per_asset=1.0, min_ticket=10.0)
    fii = next(r for r in ranking if r.ticker == "FII11")
    assert fii.suggested is not None and fii.suggested.shares > 0
    n_chosen = sum(1 for r in ranking if r.suggested)
    assert n_chosen <= 5  # respeita max_assets


def test_second_pass_reuses_rounding_leftover():
    # 2 STOCK (preços 30 e 40), aporte 200, carteira vazia -> 1a passada deixa sobra de
    # arredondamento; a 2a passada compra +1 lote onde couber, minimizando o unallocated.
    ranking = [
        ScoredAsset(ticker="AAA3", asset_class="STOCK", composite_score=0.5),
        ScoredAsset(ticker="BBB3", asset_class="STOCK", composite_score=0.5),
    ]
    prices = {"AAA3": 30.0, "BBB3": 40.0}
    lots = {"AAA3": 1, "BBB3": 1}
    targets = {"STOCK": 1.0}
    pf = Portfolio(total_value=0.0, as_of="2026-06-15T00:00:00Z", allocations=Allocations(by_class={}))
    unallocated = allocate(200.0, ranking, pf, prices, lots, targets, max_weight_per_asset=1.0, min_ticket=10.0)
    spent = sum(r.suggested.invested_exact for r in ranking if r.suggested)
    assert abs((spent + unallocated) - 200.0) < 0.05
    # sem 2a passada o gasto seria 170 (3×30 + 2×40); com ela chega a 200 (sobra ~0)
    assert spent >= 195.0 and unallocated <= 5.0
