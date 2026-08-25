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


# --- teto do aporte para o piso ---

def test_teto_limita_o_que_vai_ao_piso():
    """O caso do dono: aporte 2.000 com o teto em 50%, faltando 9.501 no piso.

    Sem o teto, o déficit come o aporte inteiro e a bolsa fica com zero — por cinco meses
    seguidos, no ritmo dele.
    """
    out = cascade.split_aporte(2_000.0, 9_501.0, 0.0, 0.0, floor_share=0.5)
    assert out["floor_directed"] == 1_000.0
    assert out["aporte_rv"] == 1_000.0
    assert out["floor_capped"] is True


def test_piso_composto_ignora_o_teto():
    """Sem déficit não há sobre o que o teto incidir: 0% e 100% dão o MESMO plano.

    É o que dispensa um `if` especial — o controle sai do cálculo sozinho.
    """
    a = cascade.split_aporte(2_000.0, 0.0, 10_000.0, 9_000.0, floor_share=0.0)
    b = cascade.split_aporte(2_000.0, 0.0, 10_000.0, 9_000.0, floor_share=1.0)
    assert a == b
    assert a["floor_directed"] == 0.0
    assert a["floor_capped"] is False


def test_teto_em_zero_nao_manda_nada_ao_piso_mesmo_com_deficit():
    out = cascade.split_aporte(1_000.0, 5_000.0, 0.0, 0.0, floor_share=0.0)
    assert out["floor_directed"] == 0.0
    assert out["aporte_rv"] == 1_000.0
    # marcado como cortado: é o que faz a tela explicar o zero em vez de silenciar
    assert out["floor_capped"] is True


def test_teto_maior_que_o_deficit_nao_inventa_aporte():
    """Teto é limite, não cota: com o piso pedindo 400 e teto de 1.000, vão 400."""
    out = cascade.split_aporte(1_000.0, 400.0, 0.0, 0.0, floor_share=1.0)
    assert out["floor_directed"] == 400.0
    assert out["floor_capped"] is False


def test_teto_fora_da_faixa_e_grampeado():
    ref = cascade.split_aporte(1_000.0, 400.0, 0.0, 0.0)
    assert cascade.split_aporte(1_000.0, 400.0, 0.0, 0.0, floor_share=1.7) == ref
    assert cascade.split_aporte(1_000.0, 400.0, 0.0, 0.0, floor_share=-0.2)["floor_directed"] == 0.0


def test_teto_em_cem_por_cento_e_identico_a_omitir():
    """A garantia de que ninguém acorda com o plano diferente: o default não muda nada."""
    for args in [
        (1_000.0, 5_000.0, 0.0, 0.0),
        (5_000.0, 300.0, 20_000.0, 19_000.0),
        (2_500.55, 1_250.27, 3_000.0, 2_999.99),
    ]:
        assert cascade.split_aporte(*args, floor_share=1.0) == cascade.split_aporte(*args)


@pytest.mark.parametrize("share", [0.0, 0.05, 0.335, 0.5, 1.0])
@pytest.mark.parametrize(
    "aporte,piso,alvo,atual",
    [
        (2_000.0, 9_501.0, 30_000.0, 12_345.67),
        (0.01, 0.02, 1.0, 0.5),
        (333.33, 111.11, 1_000.0, 950.55),
        (2_500.55, 1_250.27, 3_000.0, 2_999.99),
    ],
)
def test_conservacao_do_aporte_com_teto(aporte, piso, alvo, atual, share):
    out = cascade.split_aporte(aporte, piso, alvo, atual, floor_share=share)
    assert _soma(out) == pytest.approx(aporte, abs=1e-9)
    assert out["rf_total"] == pytest.approx(out["floor_directed"] + out["rf_directed"], abs=1e-9)
    # meio centavo de folga: o teto arredonda para o centavo mais próximo
    assert out["floor_directed"] <= aporte * share + 0.005
