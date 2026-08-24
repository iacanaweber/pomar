"""Compatibilidade de schema: um banco no v5 sobrevive às migrações novas.

O banco de produção tem dados que não existem em nenhum outro lugar — as contas e os
lançamentos da aba Reserva. A regra do projeto é que migração é ADITIVA; este arquivo é a
PROVA disso, não a promessa: monta um banco no schema v5 com dados realistas, aplica as
migrações novas e verifica linha a linha que nada se perdeu, que as colunas novas entraram
com o default que reproduz o comportamento de hoje e que as rotas antigas seguem
respondendo.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import get_db
from app.main import create_app
from app.repositories import db as db_module
from app.repositories import fixed_income_repo, preferences_repo
from app.repositories.db import Database

V5 = 5

# Colunas que existiam no v5 — a comparação "antes x depois" olha só para elas, senão as
# colunas novas (que são justamente o que a migração acrescenta) fariam o diff falhar.
_V5_COLS = {
    "preferences": (
        "id, aporte_default, targets_json, min_ticket, lot_mode, reserve_target, "
        "bazin_target_mode, bazin_target_yield, class_targets_json, updated_at"
    ),
    "fixed_income_accounts": "id, name, institution, kind, benchmark, created_at, archived",
    "fixed_income_entries": "id, account_id, kind, amount, entry_date, note",
    "portfolio_snapshots": (
        "month, total_value, annual_income, monthly_income, portfolio_yield, "
        "yield_on_cost, snapshot_json"
    ),
    "executed_orders": "id, ticker, asset_class, shares, price, fees, executed_at",
}

_TARGETS = {"STOCK": 0.50, "FII": 0.30, "ETF": 0.15, "BDR": 0.05}
_BASKETS = {"FII": {"AAA11": 0.4, "BBB11": 0.6}, "STOCK": {"AAA3": 0.55, "BBB3": 0.45}}


async def _seed_v5(path: str) -> None:
    """Cria um banco parado no v5 e o popula como um banco de uso real."""
    d = Database(path)
    await d.ensure_ready()

    await d.execute(
        """INSERT INTO preferences
               (id, aporte_default, targets_json, min_ticket, lot_mode, reserve_target,
                bazin_target_mode, bazin_target_yield, class_targets_json, updated_at)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (2500.0, json.dumps(_TARGETS), 250.0, "integral", 0.2, "fixed_6", 0.065,
         json.dumps(_BASKETS), "2026-05-01T12:00:00+00:00"),
    )

    contas = [
        (1, "Tesouro Selic 2029", "Corretora X", "tesouro", "selic", 0),
        (2, "Provisão IR 2027", "Banco Y", "conta", "cdi", 0),
        (3, "CDB antigo", "Banco Z", "cdb", "cdi", 1),
    ]
    for cid, nome, inst, kind, bench, arch in contas:
        await d.execute(
            """INSERT INTO fixed_income_accounts
                   (id, name, institution, kind, benchmark, created_at, archived)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (cid, nome, inst, kind, bench, "2025-11-02T09:00:00+00:00", arch),
        )

    lancamentos = [
        (1, "balance", 30_000.00, "2026-01-05", None),
        (1, "deposit", 2_000.00, "2026-02-10", "aporte do mês"),
        (1, "balance", 32_480.55, "2026-04-01", None),
        (2, "balance", 4_100.00, "2026-01-05", "carnê-leão"),
        (2, "deposit", 900.00, "2026-03-02", None),
        (3, "balance", 7_500.00, "2025-12-01", None),
        (3, "withdrawal", 7_500.00, "2026-01-20", "resgatei tudo"),
    ]
    for acc, kind, amount, when, note in lancamentos:
        await d.execute(
            """INSERT INTO fixed_income_entries
                   (account_id, kind, amount, entry_date, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (acc, kind, amount, when, note, f"{when}T12:00:00+00:00"),
        )

    for mes, valor, renda in (("2026-03", 118_400.0, 7_104.0), ("2026-04", 121_950.0, 7_317.0)):
        await d.execute(
            """INSERT INTO portfolio_snapshots
                   (month, created_at, total_value, annual_income, monthly_income,
                    portfolio_yield, yield_on_cost, snapshot_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (mes, f"{mes}-01T10:00:00+00:00", valor, renda, round(renda / 12, 2), 0.06, 0.081,
             json.dumps({"AAA3": {"yoc": 0.094, "annual_income": 1_200.0}})),
        )

    await d.execute(
        """INSERT INTO executed_orders
               (ticker, asset_class, shares, price, fees, executed_at, note)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("AAA3", "STOCK", 100, 28.75, 3.2, "2026-04-03T14:30:00+00:00", "aporte de abril"),
    )
    await d.close()


async def _dump(path: str) -> dict[str, list[dict]]:
    """Lê as tabelas com dados, restrito às colunas do v5, em ordem determinística."""
    d = Database(path)
    await d.ensure_ready()
    out = {
        table: await d.fetchall(f"SELECT {cols} FROM {table} ORDER BY rowid")
        for table, cols in _V5_COLS.items()
    }
    await d.close()
    return out


@pytest.fixture
async def banco_v5(monkeypatch, tmp_path):
    """Um arquivo de banco parado no schema v5, junto com o retrato dos seus dados."""
    monkeypatch.setattr(db_module, "_MIGRATIONS", [m for m in db_module._MIGRATIONS if m[0] <= V5])
    path = str(tmp_path / "v5.db")
    await _seed_v5(path)
    antes = await _dump(path)
    monkeypatch.undo()  # a partir daqui o app enxerga as migrações novas
    return path, antes


async def test_dados_do_v5_sobrevivem_as_migracoes(banco_v5):
    path, antes = banco_v5

    d = Database(path)
    await d.ensure_ready()  # aplica 6, 7 e 8
    ver = await d.fetchone("SELECT MAX(version) AS v FROM schema_migrations")
    assert ver["v"] == max(v for v, _ in db_module._MIGRATIONS)
    await d.close()

    depois = await _dump(path)
    for tabela in _V5_COLS:
        assert depois[tabela] == antes[tabela], f"{tabela} mudou na migração"


async def test_colunas_novas_entram_com_o_comportamento_de_hoje(banco_v5):
    """Default que preserva a semântica atual: nenhuma conta pré-existente passa a contar
    na carteira, e o piso da reserva nasce em zero (sem piso, sem cobrança de aporte)."""
    path, _ = banco_v5
    d = Database(path)
    await d.ensure_ready()

    contas = await d.fetchall("SELECT * FROM fixed_income_accounts ORDER BY id")
    for c in contas:
        assert c["counts_in_portfolio"] == 0
        assert c["purpose"] == "investment"
        assert c["liquidity"] == "unknown"
        assert c["redeem_days"] is None

    prefs = await d.fetchone("SELECT * FROM preferences WHERE id = 1")
    assert prefs["reserve_floor_amount"] == 0.0
    assert prefs["reserve_floor_date"] is None
    assert prefs["reserve_floor_index"] == "none"
    assert prefs["legacy_in_total"] == 1
    assert prefs["reserve_target"] == 0.2  # a coluna aposentada continua lá, intacta

    tabelas = {r["name"] for r in await d.fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"labels", "label_assignments"} <= tabelas
    await d.close()


async def test_preferencias_e_saldos_seguem_legiveis(banco_v5):
    """As leituras de domínio (não só o SELECT cru) continuam dando o mesmo número."""
    path, _ = banco_v5
    d = Database(path)
    await d.ensure_ready()

    p = await preferences_repo.get(d, Settings(_env_file=None))
    assert p["min_ticket"] == 250.0
    assert p["lot_mode"] == "integral"
    assert p["class_targets"] == _BASKETS
    assert p["targets"] == _TARGETS

    # saldo = último 'balance' + fluxos posteriores; a conta do IR tem 4.100 + 900
    resumo = {c["id"]: await fixed_income_repo.account_summary(d, c)
              for c in await fixed_income_repo.list_accounts(d, include_archived=True)}
    assert resumo[1]["current_balance"] == 32_480.55
    assert resumo[2]["current_balance"] == 5_000.00
    assert resumo[3]["current_balance"] == 0.00
    assert resumo[1]["history_yield_annual"] is not None  # rendimento segue sendo calculado
    await d.close()


def test_rotas_antigas_respondem_sobre_um_banco_v5(monkeypatch, banco_v5):
    """O cenário real do deploy: o container sobe apontando para o arquivo v5, migra no
    primeiro acesso e as rotas de sempre respondem os mesmos dados."""
    path, _ = banco_v5

    async def fake_cdi(self):
        return 0.1415

    monkeypatch.setattr("app.clients.sgs_bcb.SgsClient.cdi_annual", fake_cdi)
    monkeypatch.setenv("APP_PASSWORD", "pw")
    monkeypatch.setenv("DB_PATH", path)
    get_settings.cache_clear()
    get_db.cache_clear()
    try:
        c = TestClient(create_app(), base_url="http://testserver")
        c.post("/api/login", json={"password": "pw"})

        prefs = c.get("/api/preferences")
        assert prefs.status_code == 200
        assert prefs.json()["class_targets"] == _BASKETS

        resumo = c.get("/api/fixed-income/summary?include_archived=true")
        assert resumo.status_code == 200
        contas = {a["name"]: a for a in resumo.json()["accounts"]}
        assert contas["Tesouro Selic 2029"]["current_balance"] == 32_480.55
        assert contas["Provisão IR 2027"]["current_balance"] == 5_000.00

        entries = c.get("/api/fixed-income/accounts/1/entries")
        assert entries.status_code == 200
        assert len(entries.json()["items"]) == 3
    finally:
        get_settings.cache_clear()
        get_db.cache_clear()
