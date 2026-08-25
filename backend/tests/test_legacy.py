"""Ativos fora da carteira alvo: quem entra na conta e o que eles cobririam."""
from __future__ import annotations

import pytest

from app.services import legacy


def _pos(ticker, cls, value):
    return {"ticker": ticker, "asset_class": cls, "value": value}


TARGETS = {"STOCK": 0.6, "FII": 0.4, "ETF": 0.0, "BDR": 0.0}
BASKETS = {"STOCK": {"AAA3": 1.0}, "FII": {"CCC11": 1.0}}


# --- quem é legado ---

def test_ticker_fora_de_qualquer_cesta_e_legado():
    itens = legacy.legacy_positions(
        [_pos("AAA3", "STOCK", 600), _pos("LEGADO3", "STOCK", 100)], BASKETS, TARGETS
    )
    assert [p["ticker"] for p in itens] == ["LEGADO3"]


def test_classe_com_meta_zero_torna_a_cesta_inteira_legado():
    """O caso do enunciado: a estratégia mudou, STOCK foi a 0% e as ações seguem compradas."""
    itens = legacy.legacy_positions(
        [_pos("AAA3", "STOCK", 300), _pos("BBB3", "STOCK", 200), _pos("CCC11", "FII", 500)],
        {"STOCK": {"AAA3": 0.6, "BBB3": 0.4}, "FII": {"CCC11": 1.0}},
        {"STOCK": 0.0, "FII": 1.0},
    )
    assert [p["ticker"] for p in itens] == ["AAA3", "BBB3"]  # maior primeiro


def test_ticker_com_peso_zero_na_cesta_e_legado():
    itens = legacy.legacy_positions(
        [_pos("AAA3", "STOCK", 100)], {"STOCK": {"AAA3": 0.0, "BBB3": 1.0}}, {"STOCK": 1.0}
    )
    assert [p["ticker"] for p in itens] == ["AAA3"]


def test_posicao_de_renda_fixa_nao_e_legado():
    """Ela pertence à classe RENDA_FIXA, cuja cesta é de indexadores — não é capital de saída."""
    itens = legacy.legacy_positions(
        [_pos("IMAB11", "RENDA_FIXA", 5_000)], BASKETS, TARGETS
    )
    assert itens == []


def test_normaliza_o_ticker_do_ghostfolio():
    itens = legacy.legacy_positions([_pos("aaa3.sa", "STOCK", 100)], BASKETS, TARGETS)
    assert itens == []  # AAA3 ESTÁ na cesta; o sufixo não pode fazê-lo virar legado


def test_posicao_zerada_nao_conta():
    assert legacy.legacy_positions([_pos("ZZZ3", "STOCK", 0.0)], BASKETS, TARGETS) == []


def test_sem_carteira_alvo_tudo_e_legado():
    itens = legacy.legacy_positions([_pos("AAA3", "STOCK", 100)], {}, {})
    assert [p["ticker"] for p in itens] == ["AAA3"]


# --- cobertura do gap ---

def test_cobertura_e_a_razao_entre_legado_e_gap():
    assert legacy.coverage(5_000.0, 10_000.0) == 0.5


def test_legado_maior_que_o_gap_passa_de_100_por_cento():
    """Não é limitado a 1: saber que cobriria duas vezes o gap é a informação."""
    assert legacy.coverage(20_000.0, 10_000.0) == 2.0


def test_sem_gap_a_pergunta_nao_se_aplica():
    """None e não 0.0: 'cobriria 0% do gap' se lê como 'não adiantaria nada'."""
    assert legacy.coverage(5_000.0, 0.0) is None
    assert legacy.coverage(5_000.0, -10.0) is None


def test_resumo_junta_valor_tickers_e_cobertura():
    resumo = legacy.summarize(
        [_pos("AAA3", "STOCK", 600), _pos("LEGADO3", "STOCK", 250),
         _pos("VELHO4", "STOCK", 250)],
        gap=1_000.0,
        class_baskets=BASKETS,
        targets=TARGETS,
    )
    assert resumo["value"] == 500.0
    assert resumo["tickers"] == ["LEGADO3", "VELHO4"]
    assert resumo["gap"] == 1_000.0
    assert resumo["gap_coverage"] == 0.5


def test_sem_legado_nao_ha_resumo():
    assert legacy.summarize([_pos("AAA3", "STOCK", 600)], 1_000.0, BASKETS, TARGETS) is None


def test_soma_em_centavos_nao_perde_precisao():
    posicoes = [_pos(f"L{i}3", "STOCK", 0.07) for i in range(100)]
    resumo = legacy.summarize(posicoes, 100.0, BASKETS, TARGETS)
    assert resumo["value"] == pytest.approx(7.0, abs=1e-9)
