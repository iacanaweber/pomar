"""Piso da reserva: correção pelo IPCA, regra de liquidez e prioridade no aporte."""
from __future__ import annotations

import pytest

from app.services import reserve as r


# --- piso corrigido ---

def test_sem_indice_o_piso_e_o_nominal():
    assert r.corrected_floor(30_000.0) == {"amount": 30_000.0, "index": "none", "available": True}


def test_ipca_corrige_o_piso():
    """Um piso nominal encolhe sozinho: a correção é o que impede R$30.000 de virarem
    R$19.000 de poder de compra em dez anos sem a tela avisar."""
    out = r.corrected_floor(30_000.0, "ipca", 1.0912)
    assert out == {"amount": 32_736.0, "index": "ipca", "available": True}


def test_falha_do_ipca_cai_no_nominal_e_avisa():
    out = r.corrected_floor(30_000.0, "ipca", None)
    assert out["amount"] == 30_000.0 and out["available"] is False


def test_piso_negativo_e_tratado_como_zero():
    assert r.corrected_floor(-5.0)["amount"] == 0.0


# --- status ---

def test_status_com_piso_incompleto():
    s = r.floor_status(30_000.0, liquid_reserve=18_000.0)
    assert s["floor_corrected"] == 30_000.0
    assert s["liquid_reserve"] == 18_000.0
    assert s["deficit"] == 12_000.0
    assert s["pct_filled"] == 0.6


def test_status_com_piso_cumprido_nao_cobra_nada():
    s = r.floor_status(30_000.0, liquid_reserve=31_500.0)
    assert s["deficit"] == 0.0 and s["pct_filled"] == 1.0


def test_sem_piso_configurado_nada_falta():
    """pct_filled 0 faria a barra da tela acusar uma falta que não existe."""
    s = r.floor_status(0.0, liquid_reserve=0.0)
    assert s["deficit"] == 0.0 and s["pct_filled"] == 1.0


def test_status_guarda_o_nominal_e_o_corrigido_lado_a_lado():
    s = r.floor_status(30_000.0, 0.0, "ipca", 1.05, "2026-01-01")
    assert s["floor_nominal"] == 30_000.0
    assert s["floor_corrected"] == 31_500.0
    assert s["floor_date"] == "2026-01-01"
    assert s["index"] == "ipca" and s["index_available"] is True


# --- alvo da classe RENDA_FIXA ---

def test_alvo_da_classe_e_o_maior_entre_peso_e_piso():
    """Piso 30k, peso 20%, patrimônio 100k -> o piso manda."""
    assert r.rf_target_amount(0.20, 100_000.0, 30_000.0) == 30_000.0


def test_piso_perde_relevancia_quando_o_patrimonio_cresce():
    """Sem intervenção: a partir de 150k o percentual ultrapassa o piso e assume."""
    assert r.rf_target_amount(0.20, 150_000.0, 30_000.0) == 30_000.0
    assert r.rf_target_amount(0.20, 200_000.0, 30_000.0) == 40_000.0


def test_sem_piso_vale_so_o_percentual():
    assert r.rf_target_amount(0.20, 100_000.0, 0.0) == 20_000.0


def test_nao_existe_carve_out():
    """O alvo é calculado sobre o patrimônio INTEIRO, não sobre (patrimônio − piso): exibir
    20% de renda fixa quando a composição real é 44% seria mentir sobre a carteira."""
    assert r.rf_target_amount(0.20, 100_000.0, 0.0) == 20_000.0  # não 0.2 × (100k − piso)


# --- prioridade no aporte ---

def test_deficit_do_piso_come_o_aporte_inteiro():
    assert r.direct_to_floor(1_000.0, 12_000.0) == {"floor_directed": 1_000.0, "remaining": 0.0}


def test_aporte_maior_que_o_deficit_deixa_o_resto_para_a_renda_variavel():
    assert r.direct_to_floor(5_000.0, 3_100.0) == {"floor_directed": 3_100.0, "remaining": 1_900.0}


def test_piso_cumprido_nao_desvia_nada():
    assert r.direct_to_floor(1_000.0, 0.0) == {"floor_directed": 0.0, "remaining": 1_000.0}


def test_conservacao_do_aporte_com_centavos():
    """O que vai para o piso mais o que sobra é exatamente o aporte — sem centavo perdido
    no arredondamento."""
    for aporte, deficit in ((333.33, 111.11), (1_000.0, 999.99), (0.01, 0.02), (2_500.55, 1_250.27)):
        out = r.direct_to_floor(aporte, deficit)
        assert out["floor_directed"] + out["remaining"] == pytest.approx(aporte, abs=1e-9)
