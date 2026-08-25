"""Testes da persistência SQLite: migrações, preferências e watchlist."""
from __future__ import annotations

import os
import sqlite3

import pytest

from app.config import Settings
from app.repositories import preferences_repo, watchlist_repo
from app.repositories import db as db_module
from app.repositories.db import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.ensure_ready()
    yield database
    await database.close()


@pytest.fixture
def settings():
    return Settings(_env_file=None)


async def test_migrations_create_tables(db):
    rows = await db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    names = {r["name"] for r in rows}
    assert {
        "preferences", "watchlist", "scenarios", "plan_history", "executed_orders", "alerts",
        "fixed_income_accounts", "fixed_income_entries", "portfolio_snapshots",
    } <= names
    ver = await db.fetchone("SELECT MAX(version) AS v FROM schema_migrations")
    assert ver["v"] == max(v for v, _ in db_module._MIGRATIONS)


async def test_preferences_defaults_when_empty(db, settings):
    p = await preferences_repo.get(db, settings)
    assert p["min_ticket"] == 100.0
    assert p["class_targets"] == {}
    assert abs(sum(p["targets"].values()) - 1.0) < 0.01


async def test_preferences_put_then_get(db, settings):
    await preferences_repo.put(db, {"lot_mode": "integral", "aporte_default": 1500.0}, settings)
    p = await preferences_repo.get(db, settings)
    assert p["lot_mode"] == "integral"
    assert p["aporte_default"] == 1500.0
    # patch parcial preserva o resto
    await preferences_repo.put(db, {"min_ticket": 250.0}, settings)
    p = await preferences_repo.get(db, settings)
    assert p["lot_mode"] == "integral" and p["min_ticket"] == 250.0


async def test_watchlist_seed_is_idempotent(db):
    first = await watchlist_repo.seed_if_empty(db)
    assert first > 0
    assert await watchlist_repo.seed_if_empty(db) == 0


async def test_db_survives_reopen(tmp_path, settings):
    """Prova que a persistência depende só do arquivo (logo, do volume Docker): gravar,
    fechar a conexão e reabrir OUTRA instância no mesmo path preserva os dados."""
    path = str(tmp_path / "persist.db")
    first = Database(path)
    await first.ensure_ready()
    await preferences_repo.put(first, {"min_ticket": 900.0}, settings)
    await first.close()

    second = Database(path)
    await second.ensure_ready()
    p = await preferences_repo.get(second, settings)
    assert p["min_ticket"] == 900.0
    await second.close()


async def test_migracao_com_erro_nao_deixa_rastro(tmp_path, monkeypatch):
    """Atomicidade: se uma migração falha no meio, NADA dela é aplicado (nem a versão).
    Antes, `executescript` comitava a parte boa e o boot seguinte re-executava a
    migração — ALTER TABLE estourava 'duplicate column' e derrubava todas as rotas."""
    path = str(tmp_path / "atomic.db")
    bad = (
        99,
        """
        CREATE TABLE meia_migracao (id INTEGER PRIMARY KEY);
        INSERT INTO tabela_que_nao_existe VALUES (1);
        """,
    )
    monkeypatch.setattr(db_module, "_MIGRATIONS", db_module._MIGRATIONS + [bad])
    broken = Database(path)
    with pytest.raises(sqlite3.OperationalError):
        await broken.ensure_ready()

    # reabre com as migrações corretas: a 99 não deixou rastro e o app sobe normal
    monkeypatch.setattr(db_module, "_MIGRATIONS", [m for m in db_module._MIGRATIONS if m[0] != 99])
    recovered = Database(path)
    await recovered.ensure_ready()
    tables = {r["name"] for r in await recovered.fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "meia_migracao" not in tables
    ver = await recovered.fetchone("SELECT MAX(version) AS v FROM schema_migrations")
    assert ver["v"] == max(v for v, _ in db_module._MIGRATIONS)
    await recovered.close()


async def test_migracao_reexecutada_e_inofensiva(tmp_path):
    """ensure_ready em instância nova sobre o mesmo arquivo não re-aplica nada."""
    path = str(tmp_path / "rerun.db")
    for _ in range(2):
        d = Database(path)
        await d.ensure_ready()
        await d.close()


async def test_backup_snapshot_e_retencao(tmp_path, settings):
    path = str(tmp_path / "orig.db")
    d = Database(path)
    await d.ensure_ready()
    await preferences_repo.put(d, {"min_ticket": 700.0}, settings)

    dest_dir = str(tmp_path / "backups")
    # snapshots antigos para exercitar a retenção
    os.makedirs(dest_dir)
    for stamp in ("20200101", "20200102", "20200103"):
        with open(os.path.join(dest_dir, f"pomar-{stamp}.db"), "wb"):
            pass
    dest = await d.backup_now(dest_dir, retention=3)
    await d.close()

    # o snapshot é um banco íntegro com os dados
    restored = Database(dest)
    await restored.ensure_ready()
    p = await preferences_repo.get(restored, settings)
    assert p["min_ticket"] == 700.0
    await restored.close()

    remaining = sorted(os.listdir(dest_dir))
    assert len(remaining) == 3 and os.path.basename(dest) in remaining
    assert "pomar-20200101.db" not in remaining  # o mais antigo saiu


async def test_watchlist_crud(db):
    await watchlist_repo.add(db, "petr4", "STOCK", note="teste")
    ts = await watchlist_repo.tickers(db)
    assert "PETR4" in ts  # normalizado para maiúsculas
    await watchlist_repo.remove(db, "petr4")
    assert "PETR4" not in await watchlist_repo.tickers(db)


async def test_class_targets_column_exists(db):
    cols = {r["name"] for r in await db.fetchall("PRAGMA table_info(preferences)")}
    assert "class_targets_json" in cols


async def test_class_targets_roundtrip(db, settings):
    """A carteira alvo é o dado mais precioso das preferências: gravar, reler e sobreviver
    a um patch parcial de outro campo."""
    p = await preferences_repo.get(db, settings)
    assert p["class_targets"] == {}
    baskets = {
        "FII": {"AAA11": 0.4, "BBB11": 0.3, "CCC11": 0.3},
        # pesos com 4 casas de propósito: a carteira alvo é fina (ex.: 43,21%)
        "STOCK": {"AAA3": 0.4321, "BBB3": 0.3210, "CCC3": 0.2469},
    }
    await preferences_repo.put(db, {"class_targets": baskets}, settings)
    p = await preferences_repo.get(db, settings)
    assert p["class_targets"] == baskets
    await preferences_repo.put(db, {"min_ticket": 700.0}, settings)
    p = await preferences_repo.get(db, settings)
    assert p["class_targets"] == baskets


async def test_snapshot_mensal_grava_uma_vez_e_le_yoc(db):
    from app.repositories import snapshots_repo

    income = {
        "total_value": 50_000.0, "annual_income": 3_000.0, "monthly_income": 250.0,
        "portfolio_yield": 0.06, "yield_on_cost": 0.08,
        "by_asset": [{"ticker": "AAA3", "yield_on_cost": 0.11, "annual_income": 900.0}],
    }
    assert await snapshots_repo.save_if_new_month(db, income) is True
    assert await snapshots_repo.save_if_new_month(db, income) is False  # 1 por mês
    rows = await snapshots_repo.list_all(db)
    assert len(rows) == 1 and rows[0]["total_value"] == 50_000.0
    hist = await snapshots_repo.yoc_history(db, "aaa3")
    assert len(hist) == 1 and hist[0]["yoc"] == 0.11
    # carteira vazia nunca vira histórico
    assert await snapshots_repo.save_if_new_month(db, {"total_value": 0.0}) is False


async def test_reserve_floor_share_nasce_em_cem_por_cento(db, settings):
    """O default preserva o comportamento: quem não configurar nada não vê diferença."""
    assert (await preferences_repo.get(db, settings))["reserve_floor_share"] == 1.0
    cols = {r["name"] for r in await db.fetchall("PRAGMA table_info(preferences)")}
    assert "reserve_floor_share" in cols


async def test_reserve_floor_share_zero_sobrevive_ao_roundtrip(db, settings):
    """0% é uma ESCOLHA ("não mande nada para o piso"), não ausência de valor.

    Um `or 1.0` na leitura a transformaria em 100% em silêncio — exatamente o oposto do
    que o usuário pediu, e sem nenhum sinal de que aconteceu.
    """
    await preferences_repo.put(db, {"reserve_floor_share": 0.0}, settings)
    assert (await preferences_repo.get(db, settings))["reserve_floor_share"] == 0.0

    # e sobrevive a um patch de OUTRO campo (o merge não pode reintroduzir o default)
    await preferences_repo.put(db, {"min_ticket": 700.0}, settings)
    lidas = await preferences_repo.get(db, settings)
    assert lidas["reserve_floor_share"] == 0.0
    assert lidas["min_ticket"] == 700.0


async def test_reserve_floor_share_intermediario_persiste(db, settings):
    await preferences_repo.put(db, {"reserve_floor_share": 0.35}, settings)
    assert (await preferences_repo.get(db, settings))["reserve_floor_share"] == 0.35
