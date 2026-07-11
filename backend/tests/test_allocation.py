"""Testes da alocação do aporte (v2): need-based, slots por classe, 2ª passada, conservação."""
from __future__ import annotations

from app.models.portfolio import Allocations, Portfolio, Position
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


# --- carteira alvo (cesta por classe) ---


def _fii_portfolio(values: dict[str, float]) -> Portfolio:
    total = sum(values.values())
    return Portfolio(
        total_value=total,
        as_of="2026-07-10T00:00:00Z",
        positions=[
            Position(ticker=t, asset_class="FII", value=v, weight=v / total)
            for t, v in values.items()
        ],
        allocations=Allocations(by_class={"FII": 1.0}),
    )


def _fii_ranking(tickers: list[str], score: float = 0.5) -> list[ScoredAsset]:
    return [ScoredAsset(ticker=t, asset_class="FII", composite_score=score) for t in tickers]


def test_basket_buys_deficit_not_score():
    """Quem está acima do peso-alvo recebe 0; o déficit inteiro vai para quem falta —
    mesmo que o score diga o contrário (a cesta é matemática de rebalanceamento)."""
    pf = _fii_portfolio({"BTGL11": 5000.0, "HGRE11": 3000.0})
    ranking = [
        ScoredAsset(ticker="BTGL11", asset_class="FII", composite_score=0.9),
        ScoredAsset(ticker="HGRE11", asset_class="FII", composite_score=0.9),
        ScoredAsset(ticker="KNCR11", asset_class="FII", composite_score=0.0),  # score não manda
    ]
    prices = {"BTGL11": 100.0, "HGRE11": 50.0, "KNCR11": 10.0}
    lots = {t: 1 for t in prices}
    basket = {"BTGL11": 0.4, "HGRE11": 0.3, "KNCR11": 0.3}
    # total resultante da cesta = 8000 + 2000 = 10000 -> alvos 4000/3000/3000;
    # BTGL11 (5000) e HGRE11 (3000) já no alvo ou acima; déficit todo do KNCR11 (3000)
    unallocated = allocate(
        2000.0, ranking, pf, prices, lots, {"FII": 1.0},
        min_ticket=50.0, class_baskets={"FII": basket},
    )
    kncr = next(r for r in ranking if r.ticker == "KNCR11")
    assert kncr.suggested is not None and kncr.suggested.shares == 200
    assert next(r for r in ranking if r.ticker == "BTGL11").suggested is None
    assert next(r for r in ranking if r.ticker == "HGRE11").suggested is None
    spent = sum(r.suggested.invested_exact for r in ranking if r.suggested)
    assert abs((spent + unallocated) - 2000.0) < 0.05


def test_basket_ignores_max_assets_and_asset_cap():
    """Os pesos da cesta são a vontade explícita do usuário: max_assets e o teto por
    ativo não podem esganar a cesta."""
    pf = Portfolio(total_value=0.0, as_of="2026-07-10T00:00:00Z", allocations=Allocations())
    tickers = ["AAA11", "BBB11", "CCC11"]
    ranking = _fii_ranking(tickers)
    prices = {t: 10.0 for t in tickers}
    lots = {t: 1 for t in tickers}
    basket = {t: 1 / 3 for t in tickers}
    unallocated = allocate(
        3000.0, ranking, pf, prices, lots, {"FII": 1.0},
        max_assets=1, max_weight_per_asset=0.05, min_ticket=50.0,
        class_baskets={"FII": basket},
    )
    bought = [r for r in ranking if r.suggested]
    assert len(bought) == 3  # todos, apesar de max_assets=1
    for r in bought:
        assert abs(r.suggested.invested_exact - 1000.0) < 15.0  # ~1/3 cada, apesar do teto 5%
    assert unallocated < 30.0


def test_basket_second_pass_fills_largest_remaining_deficit():
    """Sobra de arredondamento volta para quem está mais longe do alvo, em lotes."""
    pf = Portfolio(total_value=0.0, as_of="2026-07-10T00:00:00Z", allocations=Allocations())
    ranking = _fii_ranking(["AAA11", "BBB11"])
    prices = {"AAA11": 30.0, "BBB11": 40.0}
    lots = {"AAA11": 1, "BBB11": 1}
    basket = {"AAA11": 0.5, "BBB11": 0.5}
    # 1ª passada: 100/100 -> 3×30=90 e 2×40=80 (sobra 30); 2ª: BBB (déficit 20) não cabe,
    # AAA (déficit 10, custo 30 <= sobra) compra +1 e fecha em 200
    unallocated = allocate(
        200.0, ranking, pf, prices, lots, {"FII": 1.0},
        min_ticket=10.0, class_baskets={"FII": basket},
    )
    aaa = next(r for r in ranking if r.ticker == "AAA11").suggested
    bbb = next(r for r in ranking if r.ticker == "BBB11").suggested
    assert aaa and aaa.shares == 4 and bbb and bbb.shares == 2
    assert unallocated == 0.0


def test_basket_renormalizes_when_ticker_has_no_price():
    pf = Portfolio(total_value=0.0, as_of="2026-07-10T00:00:00Z", allocations=Allocations())
    ranking = _fii_ranking(["AAA11", "BBB11", "CCC11"])
    prices = {"AAA11": 10.0, "BBB11": 10.0, "CCC11": 0.0}  # CCC11 sem cotação
    lots = {t: 1 for t in prices}
    basket = {"AAA11": 0.5, "BBB11": 0.25, "CCC11": 0.25}
    allocate(
        900.0, ranking, pf, prices, lots, {"FII": 1.0},
        min_ticket=10.0, class_baskets={"FII": basket},
    )
    aaa = next(r for r in ranking if r.ticker == "AAA11").suggested
    bbb = next(r for r in ranking if r.ticker == "BBB11").suggested
    ccc = next(r for r in ranking if r.ticker == "CCC11").suggested
    # pesos renormalizados sem CCC11: 2/3 e 1/3
    assert aaa and abs(aaa.invested_exact - 600.0) < 15.0
    assert bbb and abs(bbb.invested_exact - 300.0) < 15.0
    assert ccc is None


def test_basket_respects_min_ticket():
    pf = Portfolio(total_value=0.0, as_of="2026-07-10T00:00:00Z", allocations=Allocations())
    ranking = _fii_ranking(["AAA11", "BBB11"])
    prices = {"AAA11": 10.0, "BBB11": 10.0}
    lots = {"AAA11": 1, "BBB11": 1}
    unallocated = allocate(
        100.0, ranking, pf, prices, lots, {"FII": 1.0},
        min_ticket=100.0, class_baskets={"FII": {"AAA11": 0.5, "BBB11": 0.5}},
    )
    # 50 por ticker < ticket mínimo de 100 -> nada aberto (mesma regra do ramo por score)
    assert unallocated == 100.0
    assert all(r.suggested is None for r in ranking)


def test_focus_targets_single_class_gets_all_budget():
    """Com foco (targets = {classe: 1.0}), nenhuma outra classe recebe compra."""
    ranking = [
        ScoredAsset(ticker="MXRF11", asset_class="FII", composite_score=0.5),
        ScoredAsset(ticker="BBAS3", asset_class="STOCK", composite_score=0.9),
    ]
    prices = {"MXRF11": 10.0, "BBAS3": 28.0}
    lots = {"MXRF11": 1, "BBAS3": 1}
    pf = _portfolio(by_class={"STOCK": 0.9, "FII": 0.1})
    unallocated = allocate(
        1000.0, ranking, pf, prices, lots, {"FII": 1.0},
        max_weight_per_asset=1.0, min_ticket=50.0,
    )
    fii = next(r for r in ranking if r.ticker == "MXRF11")
    stock = next(r for r in ranking if r.ticker == "BBAS3")
    assert fii.suggested is not None and fii.suggested.shares == 100
    assert stock.suggested is None
    assert unallocated == 0.0
