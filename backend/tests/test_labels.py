"""Rótulos por dimensão: seed, integridade dos pesos e o default de geografia."""
from __future__ import annotations

import pytest

from app.data import geography
from app.data.labels_seed import BUILTIN_LABELS
from app.repositories import labels_repo as repo
from app.repositories.db import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "labels.db"))
    await database.ensure_ready()
    yield database
    await database.close()


async def _label(db: Database, dimension: str, code: str) -> int:
    row = await repo.find_label(db, dimension, code)
    assert row is not None, f"rótulo embutido {dimension}/{code} não foi semeado"
    return row["id"]


# --- seed ---

async def test_seed_dos_embutidos_e_idempotente(db):
    assert await repo.ensure_builtins(db) == len(BUILTIN_LABELS)
    assert await repo.ensure_builtins(db) == 0
    dims = {r["dimension"] for r in await repo.list_labels(db)}
    assert dims == {"bucket", "indexer", "geography"}
    assert {r["code"] for r in await repo.list_labels(db, "geography")} == {"BR", "INTL"}


async def test_embutido_nao_pode_ser_removido(db):
    cdi = await _label(db, "indexer", "CDI")
    with pytest.raises(ValueError):
        await repo.delete_label(db, cdi)


async def test_criacao_livre_e_remocao_de_rotulo_do_usuario(db):
    await repo.ensure_builtins(db)
    novo = await repo.create_label(db, "indexer", "cdb pos", "CDB pós-fixado")
    assert novo["code"] == "CDB_POS" and novo["builtin"] == 0
    with pytest.raises(ValueError):  # duplicado
        await repo.create_label(db, "indexer", "CDB_POS", "outro")
    await repo.delete_label(db, novo["id"])
    assert await repo.find_label(db, "indexer", "CDB_POS") is None


async def test_dimensao_desconhecida_e_recusada(db):
    with pytest.raises(ValueError):
        await repo.create_label(db, "setor", "BANCOS", "Bancos")


# --- atribuições ---

async def test_pesos_da_mesma_dimensao_precisam_somar_um(db):
    br, intl = await _label(db, "geography", "BR"), await _label(db, "geography", "INTL")
    with pytest.raises(ValueError):
        await repo.set_assignments(db, "ticker", "AAA11", "geography", [
            {"label_id": br, "weight": 0.6}, {"label_id": intl, "weight": 0.6},
        ])
    assert await repo.list_assignments(db, subject_type="ticker", subject_id="AAA11") == []


async def test_exposicao_parcial_e_aceita(db):
    """ETF global que inclui o Brasil: 60% internacional, 40% Brasil."""
    br, intl = await _label(db, "geography", "BR"), await _label(db, "geography", "INTL")
    rows = await repo.set_assignments(db, "ticker", "aaa11", "geography", [
        {"label_id": intl, "weight": 0.6}, {"label_id": br, "weight": 0.4},
    ])
    assert {r["code"]: r["weight"] for r in rows} == {"INTL": 0.6, "BR": 0.4}
    porsujeito = await repo.assignments_by_subject(db, "geography", "ticker")
    assert sum(i["weight"] for i in porsujeito["AAA11"]) == pytest.approx(1.0)


async def test_bucket_aceita_um_rotulo_so(db):
    rf = await _label(db, "bucket", "RENDA_FIXA")
    etf = await _label(db, "bucket", "ETF")
    with pytest.raises(ValueError):
        await repo.set_assignments(db, "ticker", "AAA11", "bucket", [
            {"label_id": rf, "weight": 0.5}, {"label_id": etf, "weight": 0.5},
        ])
    # e o peso é forçado a 1.0 mesmo se vier outro valor
    rows = await repo.set_assignments(db, "ticker", "AAA11", "bucket", [
        {"label_id": rf, "weight": 0.5},
    ])
    assert rows[0]["weight"] == 1.0
    assert await repo.bucket_overrides(db) == {"AAA11": "RENDA_FIXA"}


async def test_rotulo_de_outra_dimensao_e_recusado(db):
    cdi = await _label(db, "indexer", "CDI")
    with pytest.raises(ValueError):
        await repo.set_assignments(db, "ticker", "AAA11", "geography", [{"label_id": cdi}])


async def test_substituicao_troca_so_a_dimensao_pedida(db):
    intl = await _label(db, "geography", "INTL")
    br = await _label(db, "geography", "BR")
    cdi = await _label(db, "indexer", "CDI")
    await repo.set_assignments(db, "ticker", "AAA11", "geography", [{"label_id": intl}])
    await repo.set_assignments(db, "ticker", "AAA11", "indexer", [{"label_id": cdi}])
    await repo.set_assignments(db, "ticker", "AAA11", "geography", [{"label_id": br}])
    todos = await repo.list_assignments(db, subject_type="ticker", subject_id="AAA11")
    assert {(r["dimension"], r["code"]) for r in todos} == {("geography", "BR"), ("indexer", "CDI")}


async def test_lista_vazia_limpa_a_dimensao(db):
    br = await _label(db, "geography", "BR")
    await repo.set_assignments(db, "ticker", "AAA11", "geography", [{"label_id": br}])
    assert await repo.set_assignments(db, "ticker", "AAA11", "geography", []) == []


async def test_ticker_e_normalizado_como_no_resto_do_app(db):
    """O Ghostfolio devolve 'AAA11.SA'; o rótulo precisa cair na mesma chave."""
    br = await _label(db, "geography", "BR")
    await repo.set_assignments(db, "ticker", "aaa11.sa", "geography", [{"label_id": br}])
    rows = await repo.list_assignments(db, subject_type="ticker", subject_id="AAA11")
    assert len(rows) == 1 and rows[0]["subject_id"] == "AAA11"


async def test_conta_de_renda_fixa_tambem_recebe_indexador(db):
    ipca = await _label(db, "indexer", "IPCA")
    rows = await repo.set_assignments(db, "fi_account", "7", "indexer", [{"label_id": ipca}])
    assert rows[0]["subject_id"] == "7" and rows[0]["code"] == "IPCA"


async def test_apagar_rotulo_do_usuario_leva_as_atribuicoes_junto(db):
    await repo.ensure_builtins(db)
    novo = await repo.create_label(db, "indexer", "LCI_90", "LCI 90% CDI")
    await repo.set_assignments(db, "fi_account", "1", "indexer", [{"label_id": novo["id"]}])
    await repo.delete_label(db, novo["id"])
    assert await repo.list_assignments(db, subject_type="fi_account", subject_id="1") == []


# --- geografia default ---

@pytest.mark.parametrize(
    "ticker,esperado,origem",
    [
        ("IVVB11", "INTL", "curated"),   # S&P 500 na B3
        ("BOVA11", "BR", "curated"),     # o sufixo é o mesmo do IVVB11 — por isso o mapa existe
        ("IMAB11", "BR", "curated"),
        ("AAPL34", "INTL", "curated"),
        ("PETR4", "BR", "curated"),
        ("MXRF11", "BR", "curated"),
        ("XXXX34", "INTL", "suffix"),    # BDR fora do mapa: o sufixo resolve
        ("ZZZZ3", "BR", "fallback"),     # tudo aqui é negociado na B3
    ],
)
def test_geografia_default(ticker, esperado, origem):
    assert geography.resolve(ticker) == (esperado, origem)


def test_geografia_normaliza_sufixo_do_ghostfolio():
    assert geography.default_geography("ivvb11.sa") == "INTL"


def test_unit_que_termina_em_11_nao_vira_bdr():
    """TAEE11 e SAPR11 são ações, não BDR — a heurística olha só os sufixos de BDR."""
    assert not geography.is_bdr_ticker("TAEE11")
    assert geography.is_bdr_ticker("MSFT34")
