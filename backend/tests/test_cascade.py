"""Cascata do aporte: piso → peso da renda fixa → renda variável."""
from __future__ import annotations

import pytest

from app.services import cascade


def _soma(out: dict) -> float:
    return out["floor_directed"] + out["rf_directed"] + out["aporte_rv"]


# --- ordem de prioridade ---

def test_piso_vem_antes_de_tudo():
    out = cascade.split_aporte(1_000.0, floor_deficit=5_000.0, rf_class_target=0.0, rf_value=0.0)
    assert out["floor_directed"] == 1_000.0
    assert out["rf_directed"] == 0.0
    assert out["aporte_rv"] == 0.0


def test_sobra_do_piso_vai_para_o_peso_da_classe():
    # piso pede 300; a classe pede 20.000 e tem 19.000 => 1.000 de déficit percentual
    out = cascade.split_aporte(
        1_000.0, floor_deficit=300.0, rf_class_target=20_000.0, rf_value=19_000.0
    )
    assert out["floor_directed"] == 300.0
    # o que foi ao piso já engordou a classe: falta 20.000 − (19.000 + 300) = 700
    assert out["rf_directed"] == 700.0
    assert out["aporte_rv"] == 0.0


def test_o_que_sobra_dos_dois_vai_para_a_renda_variavel():
    out = cascade.split_aporte(
        5_000.0, floor_deficit=300.0, rf_class_target=20_000.0, rf_value=19_000.0
    )
    assert out["floor_directed"] == 300.0
    assert out["rf_directed"] == 700.0
    assert out["aporte_rv"] == 4_000.0


def test_piso_e_peso_nao_cobram_o_mesmo_dinheiro_duas_vezes():
    """O que foi ao piso conta para o peso: são a mesma classe."""
    out = cascade.split_aporte(
        1_000.0, floor_deficit=1_000.0, rf_class_target=30_000.0, rf_value=29_000.0
    )
    assert out["floor_directed"] == 1_000.0
    assert out["rf_directed"] == 0.0  # o piso já fechou o déficit percentual
    assert out["rf_total"] == 1_000.0


def test_renda_fixa_acima_do_alvo_manda_tudo_para_a_renda_variavel():
    """Gap zero, sem erro e sem aviso: é uma carteira que não precisa de aporte ali."""
    out = cascade.split_aporte(
        1_000.0, floor_deficit=0.0, rf_class_target=10_000.0, rf_value=25_000.0
    )
    assert out["floor_directed"] == 0.0
    assert out["rf_directed"] == 0.0
    assert out["aporte_rv"] == 1_000.0


def test_sem_piso_e_sem_meta_de_renda_fixa_nada_e_desviado():
    out = cascade.split_aporte(1_000.0, 0.0, 0.0, 0.0)
    assert out["aporte_rv"] == 1_000.0


def test_valores_negativos_sao_tratados_como_zero():
    out = cascade.split_aporte(1_000.0, -50.0, -10.0, -5.0)
    assert out["aporte_rv"] == 1_000.0
    assert _soma(out) == 1_000.0


# --- invariante de conservação ---

@pytest.mark.parametrize(
    "aporte,piso,alvo,atual",
    [
        (1_000.0, 300.0, 20_000.0, 19_000.0),
        (333.33, 111.11, 1_000.0, 950.55),
        (0.01, 0.02, 1.0, 0.5),
        (7_777.77, 0.0, 12_345.67, 9_876.54),
        (100.0, 5_000.0, 50_000.0, 0.0),
        (2_500.55, 1_250.27, 3_000.0, 2_999.99),
    ],
)
def test_conservacao_do_aporte(aporte, piso, alvo, atual):
    """`floor_directed + rf_directed + aporte_rv == aporte`, sem centavo perdido."""
    out = cascade.split_aporte(aporte, piso, alvo, atual)
    assert _soma(out) == pytest.approx(aporte, abs=1e-9)
    assert out["rf_total"] == pytest.approx(
        out["floor_directed"] + out["rf_directed"], abs=1e-9
    )


# --- gap da classe ---

def test_gap_em_reais_e_em_pontos_percentuais():
    gap = cascade.rf_gap(rf_class_target=20_000.0, rf_value=12_000.0, total_after=100_000.0)
    assert gap["brl"] == 8_000.0
    assert gap["pp"] == 8.0


def test_gap_zero_quando_acima_do_alvo():
    gap = cascade.rf_gap(10_000.0, 25_000.0, 100_000.0)
    assert gap["brl"] == 0.0 and gap["pp"] == 0.0


def test_gap_sem_patrimonio_nao_divide_por_zero():
    gap = cascade.rf_gap(10_000.0, 0.0, 0.0)
    assert gap["brl"] == 10_000.0 and gap["pp"] == 0.0
