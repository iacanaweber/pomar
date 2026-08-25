"""Captura semanal: recuperação, lacunas, congelamento e o benchmark composto."""
from __future__ import annotations

from datetime import date

import pytest

from app.repositories import weekly_repo
from app.repositories.db import Database
from app.services import benchmarks as bm
from app.services import weekly

D = date.fromisoformat


@pytest.fixture
async def db(tmp_path):
    d = Database(str(tmp_path / "weekly.db"))
    await d.ensure_ready()
    yield d
    await d.close()


class _Ghostfolio:
    """Carteira e transações estáveis, sem rede."""

    def __init__(self, total=10_000.0, activities=None, fail=False):
        self.total, self._acts, self.fail = total, activities or [], fail

    async def get_activities(self):
        if self.fail:
            raise RuntimeError("sem rede")
        return list(self._acts)


def _stub_portfolio(monkeypatch, total, posicoes=None):
    from app.models.portfolio import Allocations, Portfolio, Position

    async def fake(gf, cache, overrides=None):
        return Portfolio(
            total_value=total, as_of="2026-06-01T00:00:00Z", allocations=Allocations(),
            positions=[Position(ticker=t, asset_class="STOCK", value=v, weight=1.0)
                       for t, v in (posicoes or [("AAA3", total)]) if v > 0],
        )

    monkeypatch.setattr("app.services.portfolio_service.get_enriched_portfolio", fake)


async def _captura(db, monkeypatch, *, total, quando, activities=None, gf_fail=False):
    _stub_portfolio(monkeypatch, total)
    return await weekly.capture_week(
        db, _Ghostfolio(total, activities, gf_fail), cache=None, when=quando
    )


# --- semana e congelamento ---

async def test_primeira_captura_abre_a_serie_com_twr_zero(db, monkeypatch):
    """A origem da série não é um retorno de zero: é a ausência de período anterior."""
    r = await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-11"))
    assert r["saved"] is True
    assert r["week_of"] == "2026-W19"        # semana que fechou em 10/05
    assert r["week_end"] == "2026-05-10"
    assert r["twr_cumulative"] == 0.0


async def test_semana_em_curso_nao_e_capturada_como_fechada(db, monkeypatch):
    """2026-05-13 é quarta. Gravar 'o fechamento' antes do domingo criaria um ponto que
    nunca mais seria corrigido — a série é congelada."""
    r = await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-13"))
    assert r["week_end"] == "2026-05-10"     # a semana ANTERIOR, já fechada


async def test_captura_e_idempotente(db, monkeypatch):
    await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-11"))
    de_novo = await _captura(db, monkeypatch, total=99_999.0, quando=D("2026-05-11"))
    assert de_novo["saved"] is False
    assert (await weekly_repo.get_week(db, "2026-W19"))["total_value"] == 10_000.0


async def test_captura_fora_da_janela_e_marcada_como_atrasada(db, monkeypatch):
    """O container pode ter passado a semana desligado — o gráfico não pode fingir que o
    dado é do domingo."""
    r = await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-20"))
    assert r["late"] is True
    r2 = await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-25"))
    assert r2["late"] is False  # segunda seguinte ao domingo 24/05


async def test_patrimonio_zerado_nao_vira_ponto(db, monkeypatch):
    r = await _captura(db, monkeypatch, total=0.0, quando=D("2026-05-11"))
    assert r["saved"] is False


# --- o ponto do bloco: aporte não é rentabilidade ---

async def test_aporte_no_periodo_nao_vira_rentabilidade(db, monkeypatch):
    await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-11"))
    # semana seguinte: +1.000 de valor, mas foi TUDO aporte
    compra = [{"type": "BUY", "value": 1000.0, "fee": 0.0, "date": "2026-05-17",
               "ticker": "AAA3"}]
    r = await _captura(db, monkeypatch, total=11_000.0, quando=D("2026-05-18"),
                       activities=compra)
    assert r["twr_period"] == pytest.approx(0.0, abs=1e-9)
    assert r["twr_cumulative"] == pytest.approx(0.0, abs=1e-9)


async def test_valorizacao_sem_aporte_vira_retorno(db, monkeypatch):
    await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-11"))
    r = await _captura(db, monkeypatch, total=10_500.0, quando=D("2026-05-18"))
    assert r["twr_period"] == pytest.approx(0.05)


async def test_dividendo_e_creditado_como_retorno(db, monkeypatch):
    """O preço cai ex-dividendo; sem contar o provento, o TWR leria a queda como perda."""
    await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-11"))
    prov = [{"type": "DIVIDEND", "value": 200.0, "fee": 0.0, "date": "2026-05-15",
             "ticker": "AAA3"}]
    r = await _captura(db, monkeypatch, total=9_800.0, quando=D("2026-05-18"),
                       activities=prov)
    assert r["twr_period"] == pytest.approx(0.0, abs=1e-9)


async def test_ghostfolio_sem_transacoes_avisa_em_vez_de_calar(db, monkeypatch):
    """Um aporte não neutralizado superestima o retorno; o app precisa dizer isso."""
    await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-11"))
    r = await _captura(db, monkeypatch, total=11_000.0, quando=D("2026-05-18"), gf_fail=True)
    assert any("superestimado" in w for w in r["warnings"])


# --- lacunas ---

async def test_semana_perdida_vira_lacuna_e_nao_valor_inventado(db, monkeypatch):
    await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-11"))
    # pula a semana de 17/05 e captura a de 24/05
    await _captura(db, monkeypatch, total=10_500.0, quando=D("2026-05-25"))
    semanas = await weekly_repo.list_weeks(db)
    assert [w["week_of"] for w in semanas] == ["2026-W19", "2026-W21"]
    assert weekly.gaps(semanas) == ["2026-W20"]


async def test_periodo_com_lacuna_mede_contra_a_ultima_gravada(db, monkeypatch):
    """A janela é mais longa e os fluxos da lacuna inteira entram — leitura honesta de
    uma série com buraco."""
    await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-11"))
    compra = [{"type": "BUY", "value": 500.0, "fee": 0.0, "date": "2026-05-15",
               "ticker": "AAA3"}]
    r = await _captura(db, monkeypatch, total=10_500.0, quando=D("2026-05-25"),
                       activities=compra)
    assert r["twr_period"] == pytest.approx(0.0, abs=1e-6)


async def test_sem_lacuna_a_lista_fica_vazia(db, monkeypatch):
    await _captura(db, monkeypatch, total=10_000.0, quando=D("2026-05-11"))
    await _captura(db, monkeypatch, total=10_100.0, quando=D("2026-05-18"))
    assert weekly.gaps(await weekly_repo.list_weeks(db)) == []


# --- níveis dos índices ---

async def test_nivel_do_indice_e_gravado_por_data(db):
    await weekly_repo.save_level(db, "IBOV", "2026-05-08", 171_906.72, "brapi")
    await weekly_repo.save_level(db, "IBOV", "2026-05-15", 173_000.0, "brapi")
    serie = await weekly_repo.levels(db, "IBOV")
    assert [r["level"] for r in serie] == [171_906.72, 173_000.0]


async def test_regravar_a_mesma_data_atualiza_em_vez_de_duplicar(db):
    await weekly_repo.save_level(db, "CDI", "2026-05-08", 100.0)
    await weekly_repo.save_level(db, "CDI", "2026-05-08", 100.5)
    assert len(await weekly_repo.levels(db, "CDI")) == 1


# --- benchmarks (puro) ---

def test_cdi_acumula_multiplicando_nao_somando():
    """252 dias a 0,05% somam 12,6% mas capitalizam 13,4% — e o erro cresce com a janela."""
    taxas = [{"date": D("2026-01-%02d" % (i + 1)), "value": 0.05} for i in range(10)]
    serie = bm.accumulate(taxas)
    assert serie[-1]["level"] == pytest.approx(100 * 1.0005 ** 10)
    assert serie[-1]["level"] != pytest.approx(100 * (1 + 0.005))


def test_nivel_usa_o_ultimo_anterior_nunca_o_futuro():
    """Não há pregão no domingo; puxar o valor da segunda contaminaria a semana fechada."""
    serie = [{"obs_date": "2026-05-08", "level": 100.0}, {"obs_date": "2026-05-11", "level": 110.0}]
    assert bm.level_at(serie, D("2026-05-10")) == 100.0


def test_retorno_da_janela_sai_dos_niveis():
    serie = [{"obs_date": "2026-05-08", "level": 100.0}, {"obs_date": "2026-05-15", "level": 110.0}]
    assert bm.window_return(serie, D("2026-05-08"), D("2026-05-15")) == pytest.approx(0.10)


def test_serie_acumulada_parte_de_zero_no_primeiro_ponto():
    serie = [{"obs_date": "2026-05-08", "level": 100.0}, {"obs_date": "2026-05-15", "level": 110.0}]
    vals = bm.cumulative_series(serie, [D("2026-05-08"), D("2026-05-15")])
    assert vals == [pytest.approx(0.0), pytest.approx(0.10)]


def test_sem_dado_a_serie_devolve_none_sem_estourar():
    assert bm.cumulative_series([], [D("2026-05-08")]) == [None]


# --- benchmark composto ---

def test_composto_sai_dos_pesos_da_carteira_alvo():
    pesos = bm.compose_weights({"STOCK": 0.5, "FII": 0.3, "RENDA_FIXA": 0.2})
    assert pesos == {"IBOV": 0.5, "IFIX": 0.3, "CDI": 0.2}


def test_etf_se_divide_pela_geografia():
    """Sem isso, um IVVB11 seria comparado com o Ibovespa."""
    pesos = bm.compose_weights({"ETF": 1.0}, etf_geography={"INTL": 0.6})
    assert pesos["SP500BRL"] == pytest.approx(0.6)
    assert pesos["IBOV"] == pytest.approx(0.4)


def test_renda_fixa_se_divide_pelo_indexador():
    """Comparar uma carteira de IPCA+ com o CDI esconde o risco que ela assume."""
    pesos = bm.compose_weights(
        {"RENDA_FIXA": 1.0}, rf_indexers={"IPCA": 0.5, "PREFIXADO": 0.25, "CDI": 0.25}
    )
    assert pesos["IMAB"] == pytest.approx(0.5)
    assert pesos["IRFM"] == pytest.approx(0.25)
    assert pesos["CDI"] == pytest.approx(0.25)


def test_ticker_da_cesta_que_e_o_proxy_do_indice_vira_o_indice():
    """IMAB11 É o IMA-B desta tela — compará-lo com o CDI esconderia a marcação a mercado."""
    pesos = bm.compose_weights({"RENDA_FIXA": 1.0}, rf_indexers={"CDI": 0.6, "IMAB11": 0.4})
    assert pesos["CDI"] == pytest.approx(0.6)
    assert pesos["IMAB"] == pytest.approx(0.4)


def test_ticker_fora_do_mapa_cai_no_cdi_como_qualquer_item_sem_indexador():
    """Limite dos dados, não escolha: não há série do IMA-B 5+ para comparar o B5P211."""
    pesos = bm.compose_weights({"RENDA_FIXA": 1.0}, rf_indexers={"B5P211": 1.0})
    assert pesos == {"CDI": 1.0}


def test_renda_fixa_sem_cesta_cai_no_cdi():
    assert bm.compose_weights({"RENDA_FIXA": 1.0}) == {"CDI": 1.0}


def test_pesos_do_composto_somam_um():
    pesos = bm.compose_weights({"STOCK": 0.45, "FII": 0.2, "ETF": 0.05, "BDR": 0.05,
                                "RENDA_FIXA": 0.25}, etf_geography={"INTL": 1.0})
    assert sum(pesos.values()) == pytest.approx(1.0)


def test_composto_renormaliza_quando_um_indice_falta():
    """Índice sem dado não pode puxar o composto para baixo como se tivesse rendido zero."""
    series = {"IBOV": [{"obs_date": "2026-05-08", "level": 100.0},
                       {"obs_date": "2026-05-15", "level": 110.0}]}
    vals = bm.composite_series({"IBOV": 0.5, "IFIX": 0.5}, series,
                               [D("2026-05-08"), D("2026-05-15")])
    assert vals[-1] == pytest.approx(0.10)  # e não 0.05


def test_proxy_de_indice_e_declarado():
    """A tela precisa poder dizer que IFIX/IMA-B/IRF-M/S&P vêm de ETF, com taxa e
    tracking error — apresentá-los como o índice seria mentir por omissão."""
    assert bm.BENCHMARKS["IFIX"]["proxy"] == "XFIX11"
    assert bm.BENCHMARKS["SP500BRL"]["proxy"] == "IVVB11"
    assert bm.BENCHMARKS["IBOV"]["proxy"] is None
    assert bm.BENCHMARKS["CDI"]["proxy"] is None
