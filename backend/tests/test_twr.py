"""TWR, XIRR e a convenção de fluxos — o rigor que o gráfico de rendimento exige."""
from __future__ import annotations

from datetime import date

import pytest

from app.services import twr


D = date.fromisoformat


# --- convenção de sinal dos fluxos ---

def test_compra_entra_com_a_taxa_junto():
    """A taxa saiu do bolso: contá-la é o que faz o custo aparecer como perda."""
    f = twr.normalize_flows([{"type": "BUY", "value": 1000.0, "fee": 5.0, "date": "2026-05-04"}])
    assert f[0]["amount"] == 1005.0


def test_venda_sai_liquida_da_taxa():
    f = twr.normalize_flows([{"type": "SELL", "value": 1000.0, "fee": 5.0, "date": "2026-05-04"}])
    assert f[0]["amount"] == -995.0


def test_dividendo_e_saida_para_virar_retorno():
    """O preço cai ex-dividendo e o dinheiro sai do que é medido. Sem registrar a saída,
    o TWR leria a queda como prejuízo."""
    f = twr.normalize_flows([{"type": "DIVIDEND", "value": 120.0, "fee": 0, "date": "2026-05-04"}])
    assert f[0]["amount"] == -120.0


def test_dividendo_reinvestido_se_anula_e_credita_o_retorno():
    fs = twr.normalize_flows([
        {"type": "DIVIDEND", "value": 100.0, "fee": 0, "date": "2026-05-04"},
        {"type": "BUY", "value": 100.0, "fee": 0, "date": "2026-05-04"},
    ])
    assert sum(f["amount"] for f in fs) == 0.0


def test_tipo_que_nao_move_caixa_nao_vira_fluxo():
    assert twr.normalize_flows([{"type": "ITEM", "value": 500.0, "date": "2026-05-04"}]) == []


def test_saldo_de_renda_fixa_nao_e_fluxo():
    """Saldo é MEDIÇÃO. 10.000 → 10.120 não é aporte de 120, é o rendimento a medir."""
    fs = twr.fixed_income_flows([
        {"kind": "balance", "amount": 10_120.0, "entry_date": "2026-05-04"},
        {"kind": "deposit", "amount": 500.0, "entry_date": "2026-05-05"},
        {"kind": "withdrawal", "amount": 200.0, "entry_date": "2026-05-06"},
    ])
    assert [f["amount"] for f in fs] == [500.0, -200.0]


# --- janela dos fluxos ---

def test_intervalo_abre_exclusivo_e_fecha_inclusivo():
    """O que acontece no dia do fechamento pertence à semana que fecha, não à seguinte —
    senão o mesmo fluxo entra em duas semanas."""
    fs = [{"date": d, "amount": 100.0} for d in ("2026-05-03", "2026-05-04", "2026-05-10")]
    dentro = twr.flows_between(fs, D("2026-05-03"), D("2026-05-10"))
    assert [f["date"] for f in dentro] == ["2026-05-04", "2026-05-10"]


# --- retorno de um período ---

def test_sem_fluxo_o_retorno_e_a_variacao_simples():
    r = twr.period_return(10_000.0, 10_500.0, [], D("2026-05-03"), D("2026-05-10"))
    assert r["r"] == pytest.approx(0.05)
    assert r["net"] == 0.0


def test_aporte_nao_vira_rentabilidade():
    """O ponto do bloco: sem neutralizar o fluxo, qualquer carteira que aporta 'bate' o
    índice. Aportar 1.000 e terminar 1.000 acima é retorno ZERO."""
    r = twr.period_return(
        10_000.0, 11_000.0,
        [{"date": "2026-05-10", "amount": 1000.0}],  # no fim: peso 0
        D("2026-05-03"), D("2026-05-10"),
    )
    assert r["r"] == pytest.approx(0.0)


def test_fluxo_no_meio_pesa_pela_fracao_do_periodo():
    # aporte na metade do período: pesa 0.5 no capital médio
    r = twr.period_return(
        10_000.0, 11_000.0,
        [{"date": "2026-05-06", "amount": 1000.0}],
        D("2026-05-03"), D("2026-05-10"),
    )
    assert r["weighted"] == pytest.approx(1000.0 * 4 / 7, abs=0.02)
    assert r["r"] == pytest.approx(0.0, abs=1e-9)


def test_fluxo_na_abertura_pesa_integralmente():
    r = twr.period_return(
        10_000.0, 11_000.0,
        [{"date": "2026-05-04", "amount": 1000.0}],
        D("2026-05-03"), D("2026-05-10"),
    )
    assert r["weighted"] == pytest.approx(1000.0 * 6 / 7, abs=0.02)


def test_resgate_tambem_e_neutralizado():
    r = twr.period_return(
        10_000.0, 9_000.0,
        [{"date": "2026-05-10", "amount": -1000.0}],
        D("2026-05-03"), D("2026-05-10"),
    )
    assert r["r"] == pytest.approx(0.0)


def test_sem_capital_exposto_nao_ha_taxa():
    """None e não 0.0: sem denominador não existe taxa, e 0 diria 'rendeu nada'."""
    r = twr.period_return(0.0, 0.0, [], D("2026-05-03"), D("2026-05-10"))
    assert r["r"] is None


# --- encadeamento ---

def test_encadeia_multiplicando_e_nao_somando():
    assert twr.chain([0.10, 0.10]) == pytest.approx(0.21)
    assert twr.chain([0.10, 0.10]) != pytest.approx(0.20)


def test_periodos_sem_taxa_sao_pulados():
    assert twr.chain([0.05, None, 0.05]) == pytest.approx(0.1025)


def test_serie_toda_sem_taxa_nao_inventa_zero():
    assert twr.chain([None, None]) is None


def test_perda_e_ganho_se_compoem_corretamente():
    # −50% seguido de +100% volta ao ponto de partida
    assert twr.chain([-0.5, 1.0]) == pytest.approx(0.0, abs=1e-9)


# --- anualização ---

def test_janela_curta_nao_e_anualizada():
    """1% em uma semana viraria 68% ao ano, com cara de projeção."""
    assert twr.annualize(0.01, days=7) is None


def test_anualiza_janela_de_um_ano():
    assert twr.annualize(0.12, days=365) == pytest.approx(0.12, abs=1e-6)


def test_anualiza_meio_ano():
    assert twr.annualize(0.10, days=182) == pytest.approx(1.10 ** (365 / 182) - 1, abs=1e-6)


# --- XIRR ---

def test_xirr_de_um_aporte_e_um_resgate():
    r = twr.xirr([(D("2026-01-01"), -1000.0), (D("2027-01-01"), -0.0 + 1100.0)])
    assert r == pytest.approx(0.10, abs=1e-4)


def test_xirr_com_aportes_irregulares():
    fluxos = [
        (D("2026-01-01"), -1000.0),
        (D("2026-04-01"), -500.0),
        (D("2026-07-01"), -500.0),
        (D("2026-12-31"), 2150.0),
    ]
    r = twr.xirr(fluxos)
    assert r is not None and 0.0 < r < 0.5


def test_xirr_sem_troca_de_sinal_nao_tem_solucao():
    """Só aportes, sem valor final: não é erro, é uma série sem taxa."""
    assert twr.xirr([(D("2026-01-01"), -100.0), (D("2026-06-01"), -100.0)]) is None


def test_xirr_com_um_fluxo_so_e_none():
    assert twr.xirr([(D("2026-01-01"), -100.0)]) is None


def test_xirr_negativo_quando_o_dinheiro_encolheu():
    r = twr.xirr([(D("2026-01-01"), -1000.0), (D("2027-01-01"), 900.0)])
    assert r is not None and r < 0


def test_money_weighted_converte_o_sinal():
    """Na carteira o aporte é positivo; para o XIRR ele é saída do bolso."""
    r = twr.money_weighted_return(
        [{"date": "2026-01-01", "amount": 1000.0}],
        final_value=1100.0, final_date=D("2027-01-01"),
    )
    assert r == pytest.approx(0.10, abs=1e-3)


# --- semana ISO ---

def test_chave_da_semana_espelha_o_padrao_mensal():
    assert twr.week_key(D("2026-05-06")) == "2026-W19"


def test_semana_fecha_no_domingo():
    # 2026-05-06 é quarta; o domingo da semana ISO é 2026-05-10
    assert twr.week_end(D("2026-05-06")) == D("2026-05-10")
    assert twr.week_end(D("2026-05-10")) == D("2026-05-10")  # domingo é o próprio fim


def test_lista_de_domingos_entre_datas():
    ds = twr.weeks_between(D("2026-05-04"), D("2026-05-31"))
    assert ds == [D("2026-05-10"), D("2026-05-17"), D("2026-05-24"), D("2026-05-31")]
