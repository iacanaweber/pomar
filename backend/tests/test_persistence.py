"""Testes da persistência SQLite: migrações, preferências e watchlist."""
from __future__ import annotations

import pytest

from app.config import Settings
from app.repositories import preferences_repo, watchlist_repo
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
    assert {"preferences", "watchlist", "scenarios", "plan_history", "executed_orders", "alerts"} <= names
    ver = await db.fetchone("SELECT MAX(version) AS v FROM schema_migrations")
    assert ver["v"] == 1


async def test_preferences_defaults_when_empty(db, settings):
    p = await preferences_repo.get(db, settings)
    assert p["strategy"] == "equilibrado"
    assert p["max_assets"] == 5
    assert abs(sum(p["targets"].values()) - 1.0) < 0.01


async def test_preferences_put_then_get(db, settings):
    await preferences_repo.put(db, {"strategy": "bazin", "max_assets": 8}, settings)
    p = await preferences_repo.get(db, settings)
    assert p["strategy"] == "bazin"
    assert p["max_assets"] == 8
    # patch parcial preserva o resto
    await preferences_repo.put(db, {"min_ticket": 250.0}, settings)
    p = await preferences_repo.get(db, settings)
    assert p["strategy"] == "bazin" and p["min_ticket"] == 250.0


async def test_watchlist_seed_is_idempotent(db):
    first = await watchlist_repo.seed_if_empty(db)
    assert first > 0
    assert await watchlist_repo.seed_if_empty(db) == 0


async def test_watchlist_crud(db):
    await watchlist_repo.add(db, "petr4", "STOCK", note="teste")
    ts = await watchlist_repo.tickers(db)
    assert "PETR4" in ts  # normalizado para maiúsculas
    await watchlist_repo.remove(db, "petr4")
    assert "PETR4" not in await watchlist_repo.tickers(db)
