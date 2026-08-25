"""Testes do rebalanceador: déficit ao peso-alvo, need-based entre classes, sobra global."""
from __future__ import annotations

from app.models.plan import PlanAsset
from app.models.portfolio import Allocations, Portfolio, Position
from app.services.allocation import allocate


def _ranking(*tickers_classes: tuple[str, str]) -> list[PlanAsset]:
    return [PlanAsset(ticker=t, asset_class=c) for t, c in tickers_classes]


def _empty_pf() -> Portfolio:
    return Portfolio(total_value=0.0, as_of="2026-07-10T00:00:00Z", allocations=Allocations())


def _pf(values: dict[str, str | float], by_class: dict[str, float]) -> Portfolio:
    """Carteira a partir de {ticker: (classe, valor)}."""
    total = sum(v for _, v in values.values())
    return Portfolio(
        total_value=total,
        as_of="2026-07-10T00:00:00Z",
        positions=[
            Position(ticker=t, asset_class=c, value=v, weight=v / total if total else 0.0)
            for t, (c, v) in values.items()
        ],
        allocations=Allocations(by_class=by_class),
    )


def _spent(ranking: list[PlanAsset]) -> float:
    return sum(r.suggested.invested_exact for r in ranking if r.suggested)


def test_buys_the_deficit_not_the_biggest_position():
    """Quem está acima do peso-alvo recebe 0; o déficit inteiro vai para quem falta."""
    pf = _pf({"AAA11": ("FII", 5000.0), "BBB11": ("FII", 3000.0)}, {"FII": 1.0})
    ranking = _ranking(("AAA11", "FII"), ("BBB11", "FII"), ("CCC11", "FII"))
    prices = {"AAA11": 100.0, "BBB11": 50.0, "CCC11": 10.0}
    lots = {t: 1 for t in prices}
    basket = {"AAA11": 0.4, "BBB11": 0.3, "CCC11": 0.3}
    # cesta resultante = 8000 + 2000 = 10000 -> alvos 4000/3000/3000; AAA11 e BBB11 já
    # no alvo ou acima, todo o déficit (3000) é do CCC11
    unallocated = allocate(
        2000.0, ranking, pf, prices, lots, {"FII": 1.0}, {"FII": basket}, min_ticket=50.0
    )
    atrasado = next(r for r in ranking if r.ticker == "CCC11")
    assert atrasado.suggested is not None and atrasado.suggested.shares == 200
    assert next(r for r in ranking if r.ticker == "AAA11").suggested is None
    assert next(r for r in ranking if r.ticker == "BBB11").suggested is None
    assert abs((_spent(ranking) + unallocated) - 2000.0) < 0.05


def test_need_based_split_between_classes():
    """Carteira 1000 (90% STOCK / 10% FII), aporte 1000, metas 50/50: o FII (need 900)
    recebe muito mais que o STOCK (need 100) — sem jogar o FII acima do alvo."""
    pf = _pf({"SXXX3": ("STOCK", 900.0), "FXXX11": ("FII", 100.0)}, {"STOCK": 0.9, "FII": 0.1})
    ranking = _ranking(("SXXX3", "STOCK"), ("FXXX11", "FII"))
    prices = {"SXXX3": 10.0, "FXXX11": 10.0}
    lots = {t: 1 for t in prices}
    unallocated = allocate(
        1000.0, ranking, pf, prices, lots,
        {"STOCK": 0.5, "FII": 0.5},
        {"STOCK": {"SXXX3": 1.0}, "FII": {"FXXX11": 1.0}},
        min_ticket=10.0,
    )
    stock = next(r for r in ranking if r.ticker == "SXXX3").suggested
    fii = next(r for r in ranking if r.ticker == "FXXX11").suggested
    assert stock and fii
    assert fii.invested_exact > stock.invested_exact
    assert 80 <= stock.invested_exact <= 160
    assert 840 <= fii.invested_exact <= 920
    assert abs((_spent(ranking) + unallocated) - 1000.0) < 0.05


def test_leftover_of_one_class_completes_a_lot_in_another():
    """O troco que não fecha um lote na própria classe atravessa para a outra cesta."""
    ranking = _ranking(("AAA3", "STOCK"), ("BBB11", "FII"))
    prices = {"AAA3": 60.0, "BBB11": 30.0}
    lots = {t: 1 for t in prices}
    # orçamentos 100/100: AAA3 compra 1 (60, sobra 40 que não paga outro lote de 60);
    # BBB11 compra 3 (90). A sobra global de 50 fecha +1 lote de BBB11 (30).
    unallocated = allocate(
        200.0, ranking, _empty_pf(), prices, lots,
        {"STOCK": 0.5, "FII": 0.5},
        {"STOCK": {"AAA3": 1.0}, "FII": {"BBB11": 1.0}},
        min_ticket=10.0,
    )
    aaa = next(r for r in ranking if r.ticker == "AAA3").suggested
    bbb = next(r for r in ranking if r.ticker == "BBB11").suggested
    assert aaa and aaa.shares == 1
    assert bbb and bbb.shares == 4  # 3 do orçamento da classe + 1 da sobra global
    assert abs((_spent(ranking) + unallocated) - 200.0) < 0.05
    assert unallocated == 20.0


def test_leftover_never_opens_a_position_below_min_ticket():
    """A sobra completa posições existentes, mas não abre uma nova por trocados."""
    pf = _pf({"AAA3": ("STOCK", 1000.0)}, {"STOCK": 1.0})
    ranking = _ranking(("AAA3", "STOCK"), ("BBB3", "STOCK"))
    prices = {"AAA3": 40.0, "BBB3": 30.0}
    lots = {t: 1 for t in prices}
    unallocated = allocate(
        100.0, ranking, pf, prices, lots, {"STOCK": 1.0},
        {"STOCK": {"AAA3": 0.5, "BBB3": 0.5}},
        min_ticket=200.0,
    )
    # BBB3 está zerado e é quem tem o maior déficit, mas 1 lote (30) < min_ticket (200):
    # a posição não é aberta e o dinheiro sobra em vez de virar ponta
    assert next(r for r in ranking if r.ticker == "BBB3").suggested is None
    assert unallocated == 100.0


def test_leftover_tops_up_a_position_already_held():
    """Ativo que já está na carteira pode receber a sobra mesmo abaixo do min_ticket —
    o piso é para ABRIR posição, não para reforçá-la."""
    pf = _pf({"AAA3": ("STOCK", 300.0), "BBB3": ("STOCK", 700.0)}, {"STOCK": 1.0})
    ranking = _ranking(("AAA3", "STOCK"), ("BBB3", "STOCK"))
    prices = {"AAA3": 30.0, "BBB3": 70.0}
    lots = {t: 1 for t in prices}
    unallocated = allocate(
        100.0, ranking, pf, prices, lots, {"STOCK": 1.0},
        {"STOCK": {"AAA3": 0.5, "BBB3": 0.5}},
        min_ticket=500.0,
    )
    aaa = next(r for r in ranking if r.ticker == "AAA3").suggested
    assert aaa and aaa.shares == 3  # AAA3 (300 de 1100) é o mais atrasado
    assert unallocated == 10.0


def test_unmarked_class_receives_nothing():
    """Classe com cesta definida mas fora do plano (não veio em class_baskets) fica de fora."""
    ranking = _ranking(("AAA3", "STOCK"), ("BBB11", "FII"))
    prices = {"AAA3": 10.0, "BBB11": 10.0}
    lots = {t: 1 for t in prices}
    unallocated = allocate(
        1000.0, ranking, _empty_pf(), prices, lots,
        {"STOCK": 0.5, "FII": 0.5},
        {"STOCK": {"AAA3": 1.0}},  # só STOCK marcada
        min_ticket=10.0,
    )
    assert next(r for r in ranking if r.ticker == "BBB11").suggested is None
    aaa = next(r for r in ranking if r.ticker == "AAA3").suggested
    assert aaa and aaa.invested_exact == 1000.0
    assert unallocated == 0.0


def test_no_basket_at_all_returns_the_whole_aporte():
    ranking = _ranking(("AAA3", "STOCK"))
    unallocated = allocate(
        500.0, ranking, _empty_pf(), {"AAA3": 10.0}, {"AAA3": 1}, {"STOCK": 1.0}, {}
    )
    assert unallocated == 500.0
    assert ranking[0].suggested is None


def test_renormalizes_when_a_ticker_has_no_price():
    ranking = _ranking(("AAA11", "FII"), ("BBB11", "FII"), ("CCC11", "FII"))
    prices = {"AAA11": 10.0, "BBB11": 10.0, "CCC11": 0.0}  # CCC11 sem cotação
    lots = {t: 1 for t in prices}
    allocate(
        900.0, ranking, _empty_pf(), prices, lots, {"FII": 1.0},
        {"FII": {"AAA11": 0.5, "BBB11": 0.25, "CCC11": 0.25}},
        min_ticket=10.0,
    )
    aaa = next(r for r in ranking if r.ticker == "AAA11").suggested
    bbb = next(r for r in ranking if r.ticker == "BBB11").suggested
    ccc = next(r for r in ranking if r.ticker == "CCC11")
    # pesos renormalizados sem CCC11: 2/3 e 1/3
    assert aaa and abs(aaa.invested_exact - 600.0) < 15.0
    assert bbb and abs(bbb.invested_exact - 300.0) < 15.0
    assert ccc.suggested is None and ccc.basket_target_pct is None


def test_min_ticket_skips_tiny_allocations():
    ranking = _ranking(("AAA11", "FII"), ("BBB11", "FII"))
    unallocated = allocate(
        100.0, ranking, _empty_pf(), {"AAA11": 10.0, "BBB11": 10.0}, {"AAA11": 1, "BBB11": 1},
        {"FII": 1.0}, {"FII": {"AAA11": 0.5, "BBB11": 0.5}}, min_ticket=100.0,
    )
    # 50 por ticker < ticket mínimo de 100 -> nada aberto
    assert unallocated == 100.0
    assert all(r.suggested is None for r in ranking)


def test_lot_size_is_respected():
    ranking = _ranking(("AAA3", "STOCK"))
    unallocated = allocate(
        1000.0, ranking, _empty_pf(), {"AAA3": 3.0}, {"AAA3": 100}, {"STOCK": 1.0},
        {"STOCK": {"AAA3": 1.0}}, min_ticket=10.0,
    )
    s = ranking[0].suggested
    assert s and s.shares == 300 and s.lot_size == 100 and s.lot_note == "lote 100"
    assert unallocated == 100.0  # 1000 = 3 lotes de 300 + 100 que não fecham outro lote


def test_basket_view_is_filled_for_the_ui():
    """A barra da cesta (alvo / hoje / depois) sai do alocador, não é recalculada na rota."""
    pf = _pf({"AAA11": ("FII", 800.0), "BBB11": ("FII", 200.0)}, {"FII": 1.0})
    ranking = _ranking(("AAA11", "FII"), ("BBB11", "FII"))
    prices = {"AAA11": 10.0, "BBB11": 10.0}
    lots = {t: 1 for t in prices}
    allocate(
        1000.0, ranking, pf, prices, lots, {"FII": 1.0},
        {"FII": {"AAA11": 0.5, "BBB11": 0.5}}, min_ticket=10.0,
    )
    aaa = next(r for r in ranking if r.ticker == "AAA11")
    bbb = next(r for r in ranking if r.ticker == "BBB11")
    assert aaa.basket_target_pct == 0.5 and bbb.basket_target_pct == 0.5
    assert aaa.basket_current_pct == 0.8 and bbb.basket_current_pct == 0.2
    # 2000 na cesta ao fim: BBB11 sobe de 200 para 1000 (50%), AAA11 fica onde está
    assert abs(bbb.basket_after_pct - 0.5) < 0.01
    assert abs(aaa.basket_after_pct - 0.5) < 0.01
    assert bbb.basket_gap_brl == 800.0  # 0.5 × 2000 − 200
    assert aaa.basket_gap_brl == 200.0


def test_zero_target_class_gets_no_money():
    ranking = _ranking(("AAA3", "STOCK"))
    unallocated = allocate(
        500.0, ranking, _empty_pf(), {"AAA3": 10.0}, {"AAA3": 1}, {"STOCK": 0.0},
        {"STOCK": {"AAA3": 1.0}}, min_ticket=10.0,
    )
    assert ranking[0].suggested is None
    assert unallocated == 500.0


# --- ativos fora do alvo: base dos alvos em R$ ---------------------------------------

def test_legado_nao_conta_como_progresso_rumo_ao_alvo():
    """O ponto do bloco: somar o legado dentro da classe fazia ele se CANCELAR — inflava a
    base do alvo e o valor atual na mesma medida, e a classe parecia já estar no lugar."""
    from app.services.allocation import aligned_value_by_class

    held = {"AAA3": 1000.0, "VELHO4": 500.0}
    baskets = {"STOCK": {"AAA3": 1.0}}
    assert aligned_value_by_class(held, baskets, {"STOCK": 1.0}) == {"STOCK": 1000.0}


def test_classe_com_meta_zero_nao_tem_valor_alinhado():
    from app.services.allocation import aligned_value_by_class

    held = {"AAA3": 1000.0}
    alinhado = aligned_value_by_class(held, {"STOCK": {"AAA3": 1.0}}, {"STOCK": 0.0})
    assert alinhado == {}


def test_ticker_sem_cotacao_continua_sendo_capital_alinhado():
    """Falha do provedor não é decisão de estratégia: o ativo não vira legado por isso."""
    from app.services.allocation import aligned_value_by_class

    held = {"AAA3": 1000.0, "SEMPRECO3": 400.0}
    baskets = {"STOCK": {"AAA3": 0.5, "SEMPRECO3": 0.5}}
    assert aligned_value_by_class(held, baskets, {"STOCK": 1.0}) == {"STOCK": 1400.0}


def test_legado_aumenta_o_need_e_mantem_a_carteira_subalocada():
    pf = _pf({"AAA3": ("STOCK", 1000.0), "VELHO4": ("STOCK", 500.0)}, {"STOCK": 1.0})
    ranking = _ranking(("AAA3", "STOCK"))
    prices, lots = {"AAA3": 10.0}, {"AAA3": 1}

    sobra = allocate(100.0, ranking, pf, prices, lots, {"STOCK": 1.0},
                     {"STOCK": {"AAA3": 1.0}}, min_ticket=10.0)
    # o aporte inteiro é comprado: a classe segue abaixo do alvo por causa do legado
    assert _spent(ranking) == 100.0
    assert sobra == 0.0


def test_legacy_in_total_false_mira_so_o_capital_alinhado():
    """Sem o legado na base, a carteira do exemplo já está no alvo e a compra é proporcional."""
    pf = _pf({"AAA3": ("STOCK", 1000.0), "VELHO4": ("STOCK", 500.0)}, {"STOCK": 1.0})
    ranking = _ranking(("AAA3", "STOCK"))
    prices, lots = {"AAA3": 10.0}, {"AAA3": 1}

    sobra = allocate(100.0, ranking, pf, prices, lots, {"STOCK": 1.0},
                     {"STOCK": {"AAA3": 1.0}}, min_ticket=10.0, legacy_in_total=False)
    assert _spent(ranking) + sobra == 100.0  # invariante em qualquer modo


def test_invariante_de_conservacao_com_legado_e_lote():
    """`spent + unallocated == aporte`, com valores que forçam arredondamento de lote."""
    pf = _pf({"AAA3": ("STOCK", 1234.56), "VELHO4": ("STOCK", 789.01)}, {"STOCK": 1.0})
    for aporte in (333.33, 1000.0, 97.77, 5_555.55):
        for legacy_in_total in (True, False):
            ranking = _ranking(("AAA3", "STOCK"), ("BBB3", "STOCK"))
            prices = {"AAA3": 27.31, "BBB3": 13.07}
            lots = {"AAA3": 100, "BBB3": 100}  # lote inteiro: o troco é grande de propósito
            sobra = allocate(
                aporte, ranking, pf, prices, lots, {"STOCK": 1.0},
                {"STOCK": {"AAA3": 0.6, "BBB3": 0.4}}, min_ticket=100.0,
                legacy_in_total=legacy_in_total,
            )
            assert abs(_spent(ranking) + sobra - aporte) < 0.01
