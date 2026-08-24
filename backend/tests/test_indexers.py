"""Cesta de RENDA_FIXA: valor por tag de indexador e rateio do aporte entre elas."""
from __future__ import annotations

import pytest

from app.data.labels_seed import NO_INDEXER_CODE
from app.services import indexers as ix


def _conta(id_, saldo):
    return {"id": id_, "balance": saldo}


# --- valor por tag ---

def test_soma_saldos_por_tag():
    valores = ix.value_by_indexer(
        [_conta(1, 30_000.0), _conta(2, 12_000.0)],
        {"1": [{"code": "SELIC", "weight": 1.0}], "2": [{"code": "CDI", "weight": 1.0}]},
    )
    assert valores == {"SELIC": 30_000.0, "CDI": 12_000.0}


def test_conta_sem_tag_cai_no_residual_visivel():
    """Bucket residual silencioso seria pior que um errado: o dinheiro sumiria da
    composição sem nada avisar."""
    valores = ix.value_by_indexer([_conta(1, 5_000.0)], {})
    assert valores == {NO_INDEXER_CODE: 5_000.0}


def test_conta_com_duas_tags_e_rateada_pelos_pesos():
    valores = ix.value_by_indexer(
        [_conta(1, 10_000.0)],
        {"1": [{"code": "CDI", "weight": 0.6}, {"code": "IPCA", "weight": 0.4}]},
    )
    assert valores == {"CDI": 6_000.0, "IPCA": 4_000.0}


def test_rateio_nao_perde_centavo():
    """R$100 em três tags de 1/3 são 33,33 + 33,33 + 33,34 — a soma das partes é o todo."""
    valores = ix.value_by_indexer(
        [_conta(1, 100.0)],
        {"1": [{"code": c, "weight": 1 / 3} for c in ("CDI", "IPCA", "LCI")]},
    )
    assert sum(valores.values()) == pytest.approx(100.0)
    assert sorted(valores.values()) == [33.33, 33.33, 33.34]


def test_etf_de_renda_fixa_pesa_na_cesta_ao_lado_do_cdb():
    """A atribuição manual de bucket é o que permite isto: IMAB11 é um ETF e mesmo assim
    é item da cesta de renda fixa de quem o compra pelo indexador."""
    valores = ix.value_by_indexer(
        [_conta(1, 20_000.0)],
        {"1": [{"code": "SELIC", "weight": 1.0}]},
        positions=[{"ticker": "IMAB11", "value": 8_000.0}],
        ticker_labels={"IMAB11": [{"code": "IPCA", "weight": 1.0}]},
    )
    assert valores == {"SELIC": 20_000.0, "IPCA": 8_000.0}


def test_posicao_sem_tag_tambem_e_visivel():
    valores = ix.value_by_indexer([], {}, positions=[{"ticker": "AAA11", "value": 1_000.0}])
    assert valores == {NO_INDEXER_CODE: 1_000.0}


def test_saldo_zerado_nao_cria_tag_fantasma():
    assert ix.value_by_indexer([_conta(1, 0.0)], {}) == {}


# --- rateio do aporte entre as tags ---

def test_aporte_vai_para_quem_esta_mais_longe_do_alvo():
    """Mesma aritmética de _allocate_basket: proporcional ao déficit."""
    out = ix.basket_deficits(
        {"SELIC": 0.5, "IPCA": 0.5},
        current={"SELIC": 30_000.0, "IPCA": 10_000.0},
        budget=10_000.0,
    )
    # base = 50.000; alvo de cada = 25.000; só IPCA está abaixo (déficit 15.000)
    assert out == {"IPCA": 10_000.0}


def test_quem_esta_acima_do_alvo_recebe_zero():
    out = ix.basket_deficits(
        {"CDI": 0.3, "IPCA": 0.7}, current={"CDI": 50_000.0, "IPCA": 0.0}, budget=5_000.0
    )
    assert "CDI" not in out and out["IPCA"] == 5_000.0


def test_cesta_ja_no_alvo_rateia_pelos_proprios_pesos():
    """Sem isso o dinheiro ficaria parado quando todas as tags estão no lugar."""
    out = ix.basket_deficits(
        {"CDI": 0.5, "IPCA": 0.5}, current={"CDI": 0.0, "IPCA": 0.0}, budget=1_000.0
    )
    assert out == {"CDI": 500.0, "IPCA": 500.0}


def test_pesos_sao_renormalizados_entre_as_tags_da_cesta():
    out = ix.basket_deficits({"CDI": 0.2, "IPCA": 0.2}, current={}, budget=1_000.0)
    assert out == {"CDI": 500.0, "IPCA": 500.0}


def test_conservacao_do_orcamento_com_arredondamento():
    for budget in (1_000.0, 333.33, 0.03, 9_999.99):
        out = ix.basket_deficits({"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}, {}, budget)
        assert sum(out.values()) == pytest.approx(budget, abs=1e-9)


def test_sem_alvo_ou_sem_orcamento_nada_e_rateado():
    assert ix.basket_deficits({}, {"CDI": 100.0}, 1_000.0) == {}
    assert ix.basket_deficits({"CDI": 1.0}, {}, 0.0) == {}
