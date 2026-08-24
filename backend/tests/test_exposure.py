"""Composição do patrimônio: renda variável + renda fixa marcada, por dimensão."""
from __future__ import annotations

import pytest

from app.services import exposure as ex


def _pos(ticker, cls, sector, value):
    return {"ticker": ticker, "asset_class": cls, "sector": sector, "value": value}


def test_renda_fixa_marcada_entra_na_composicao():
    """Sem isto, quem tem 30% em Tesouro Selic veria uma carteira 100% em bolsa."""
    out = ex.compose(
        [_pos("AAA3", "STOCK", "Bancos", 70_000.0)],
        [{"id": 1, "balance": 30_000.0}],
    )
    assert out["total"] == 100_000.0
    assert out["by_class"] == {"STOCK": 70_000.0, "RENDA_FIXA": 30_000.0}
    assert out["by_sector"] == {"Bancos": 70_000.0, "Renda fixa": 30_000.0}


def test_geografia_usa_o_mapa_curado_quando_nao_ha_rotulo():
    out = ex.compose([
        _pos("IVVB11", "ETF", "Exterior", 10_000.0),   # curado como INTL
        _pos("BOVA11", "ETF", "Diversificado", 10_000.0),  # mesmo sufixo, curado como BR
        _pos("AAPL34", "BDR", "Exterior", 5_000.0),    # sufixo de BDR
    ])
    assert out["by_geography"] == {"INTL": 15_000.0, "BR": 10_000.0}


def test_rotulo_do_usuario_vence_o_default():
    out = ex.compose(
        [_pos("IVVB11", "ETF", "Exterior", 10_000.0)],
        geography_by_ticker={"IVVB11": [{"code": "BR", "weight": 1.0}]},
    )
    assert out["by_geography"] == {"BR": 10_000.0}


def test_exposicao_parcial_e_respeitada():
    """ETF global que inclui o Brasil: 60% internacional, 40% aqui."""
    out = ex.compose(
        [_pos("ZZZZ11", "ETF", "Diversificado", 10_000.0)],
        geography_by_ticker={
            "ZZZZ11": [{"code": "INTL", "weight": 0.6}, {"code": "BR", "weight": 0.4}]
        },
    )
    assert out["by_geography"] == {"INTL": 6_000.0, "BR": 4_000.0}
    assert sum(out["by_geography"].values()) == pytest.approx(out["total"])


def test_conta_de_renda_fixa_e_brasileira_por_default():
    out = ex.compose([], [{"id": 7, "balance": 20_000.0}])
    assert out["by_geography"] == {"BR": 20_000.0}


def test_conta_pode_receber_geografia_propria():
    out = ex.compose(
        [], [{"id": 7, "balance": 20_000.0}],
        geography_by_account={"7": [{"code": "INTL", "weight": 1.0}]},
    )
    assert out["by_geography"] == {"INTL": 20_000.0}


def test_as_dimensoes_sempre_somam_o_total():
    posicoes = [
        _pos("AAA3", "STOCK", "Bancos", 33_333.33),
        _pos("BBB11", "FII", "Imobiliário", 11_111.11),
        _pos("CCC34", "BDR", "Exterior", 7_777.77),
    ]
    out = ex.compose(posicoes, [{"id": 1, "balance": 5_555.55}])
    for chave in ("by_class", "by_sector", "by_geography"):
        assert sum(out[chave].values()) == pytest.approx(out["total"], abs=1e-9)


def test_posicao_zerada_nao_cria_fatia():
    out = ex.compose([_pos("AAA3", "STOCK", "Bancos", 0.0)], [])
    assert out["total"] == 0.0 and out["by_class"] == {}


# --- metas informativas ---

def test_meta_gera_desvio_em_pontos_percentuais():
    itens = ex.with_targets({"BR": 80_000.0, "INTL": 20_000.0}, 100_000.0, {"INTL": 0.3})
    por_code = {i["code"]: i for i in itens}
    assert por_code["INTL"]["pct"] == 0.2
    assert por_code["INTL"]["target_pct"] == 0.3
    assert por_code["INTL"]["deviation_pp"] == -10.0
    assert por_code["BR"]["target_pct"] is None  # sem meta, sem desvio inventado


def test_meta_sem_posicao_continua_visivel():
    """Exposição planejada e não montada é justamente o desvio que interessa."""
    itens = ex.with_targets({"BR": 100_000.0}, 100_000.0, {"INTL": 0.2})
    por_code = {i["code"]: i for i in itens}
    assert por_code["INTL"]["value"] == 0.0 and por_code["INTL"]["deviation_pp"] == -20.0


def test_patrimonio_zerado_nao_divide_por_zero():
    itens = ex.with_targets({}, 0.0, {"INTL": 0.2})
    assert itens[0]["pct"] == 0.0 and itens[0]["deviation_pp"] == -20.0
