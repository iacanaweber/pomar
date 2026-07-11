"""Persistência SQLite (single-user) — conexão única + migrações versionadas.

Escolha de sqlite3 puro (stdlib) em vez de um ORM: o app é pessoal, de baixo volume e
sem relações complexas — manter o backend enxuto vale mais que a comodidade do ORM.
Como o resto do app é async, toda operação roda em `asyncio.to_thread` e é serializada
por um `asyncio.Lock` (uma só conexão, single-user → contenção desprezível).
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

# Migrações versionadas: cada item é (versão, SQL). Para evoluir o schema, ADICIONE uma
# nova entrada — nunca edite uma já aplicada. O schema completo (incl. tabelas usadas só
# na Fase 2) é criado de uma vez para evitar churn de migração.
_MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS preferences (
            id                    INTEGER PRIMARY KEY CHECK (id = 1),
            strategy              TEXT    NOT NULL DEFAULT 'equilibrado',
            aporte_default        REAL,
            targets_json          TEXT,
            weights_json          TEXT,
            max_assets            INTEGER NOT NULL DEFAULT 5,
            max_weight_per_asset  REAL    NOT NULL DEFAULT 0.20,
            min_ticket            REAL    NOT NULL DEFAULT 100.0,
            lot_mode              TEXT    NOT NULL DEFAULT 'integral',
            reserve_target        REAL    NOT NULL DEFAULT 0.0,
            bazin_target_mode     TEXT    NOT NULL DEFAULT 'fixed_6',
            updated_at            TEXT
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            ticker            TEXT PRIMARY KEY,
            asset_class       TEXT NOT NULL DEFAULT 'STOCK',
            note              TEXT,
            favorite          INTEGER NOT NULL DEFAULT 0,
            added_at          TEXT,
            last_validated_at TEXT,
            valid             INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS scenarios (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            kind         TEXT,
            targets_json TEXT,
            weights_json TEXT,
            params_json  TEXT,
            created_at   TEXT,
            updated_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS plan_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at    TEXT,
            scenario_id   INTEGER,
            aporte        REAL,
            strategy      TEXT,
            request_json  TEXT,
            response_json TEXT,
            rates_json    TEXT
        );

        CREATE TABLE IF NOT EXISTS executed_orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id     INTEGER,
            ticker      TEXT NOT NULL,
            asset_class TEXT,
            shares      INTEGER,
            price       REAL,
            fees        REAL DEFAULT 0,
            executed_at TEXT,
            note        TEXT
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            kind         TEXT NOT NULL,
            ticker       TEXT,
            payload_json TEXT,
            created_at   TEXT,
            acknowledged INTEGER NOT NULL DEFAULT 0
        );
        """,
    ),
    (
        2,
        # Rastreador manual de renda fixa: contas + lançamentos (saldo/aporte/resgate).
        # O rendimento é derivado das atualizações de saldo (ver services/fixed_income.py).
        """
        CREATE TABLE IF NOT EXISTS fixed_income_accounts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            institution TEXT,
            kind        TEXT,                       -- 'cdb'|'tesouro'|'poupanca'|'conta'|'outro'
            benchmark   TEXT,                       -- 'cdi'|'selic'|'prefixado'|'ipca' (informativo)
            created_at  TEXT,
            archived    INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS fixed_income_entries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id  INTEGER NOT NULL REFERENCES fixed_income_accounts(id) ON DELETE CASCADE,
            kind        TEXT NOT NULL,              -- 'balance' | 'deposit' | 'withdrawal'
            amount      REAL NOT NULL,              -- saldo observado (balance) OU valor (deposit/withdrawal)
            entry_date  TEXT NOT NULL,              -- ISO yyyy-mm-dd
            note        TEXT,
            created_at  TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_fie_account ON fixed_income_entries(account_id, entry_date);
        """,
    ),
    (
        3,
        # Parametrização do preço-teto de Bazin + meta de renda (Aportador / objetivo).
        """
        ALTER TABLE preferences ADD COLUMN bazin_target_yield    REAL    NOT NULL DEFAULT 0.06;
        ALTER TABLE preferences ADD COLUMN target_monthly_income REAL    NOT NULL DEFAULT 0.0;
        ALTER TABLE preferences ADD COLUMN target_horizon_years  INTEGER NOT NULL DEFAULT 20;
        ALTER TABLE preferences ADD COLUMN annual_growth         REAL    NOT NULL DEFAULT 0.0;
        """,
    ),
    (
        4,
        # v4: série histórica da bola de neve REAL — um snapshot por mês (gravado
        # oportunisticamente no 1º acesso à renda do mês) + premissa de inflação e
        # opt-in de contar a renda fixa na meta. Migração ADITIVA: nada existente muda.
        """
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            month           TEXT NOT NULL UNIQUE,      -- 'yyyy-mm'
            created_at      TEXT,
            total_value     REAL,
            annual_income   REAL,                      -- estimada, líquida
            monthly_income  REAL,
            portfolio_yield REAL,
            yield_on_cost   REAL,
            snapshot_json   TEXT                       -- detalhe por ativo (yoc, renda)
        );
        ALTER TABLE preferences ADD COLUMN expected_inflation     REAL    NOT NULL DEFAULT 0.04;
        ALTER TABLE preferences ADD COLUMN include_reserve_income INTEGER NOT NULL DEFAULT 0;
        """,
    ),
    (
        5,
        # v5: foco do aporte (BALANCE ou uma classe específica) + carteira alvo por classe
        # ({"FII": {"BTGL11": 0.4, ...}}). A coluna watchlist.favorite (v1) passa a ser usada.
        """
        ALTER TABLE preferences ADD COLUMN focus              TEXT NOT NULL DEFAULT 'BALANCE';
        ALTER TABLE preferences ADD COLUMN class_targets_json TEXT;
        """,
    ),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_statements(sql: str) -> list[str]:
    """Divide um script de migração em statements individuais.

    Necessário porque `executescript` faz COMMIT implícito antes de rodar — o que
    quebra a atomicidade da migração (ver `_migrate`). O split por ';' é suficiente
    aqui: as migrações são DDL simples, sem ';' embutido em literais.
    """
    stmts: list[str] = []
    for chunk in sql.split(";"):
        # descarta fragmentos que são só comentários/vazio (ex.: cauda após o último ';')
        meaningful = any(line.split("--")[0].strip() for line in chunk.splitlines())
        if meaningful:
            stmts.append(chunk.strip())
    return stmts


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()
        self._ready = False

    # --- setup (sync, roda em thread) ---
    def _open(self) -> sqlite3.Connection:
        if self.path != ":memory:":
            parent = os.path.dirname(self.path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT)"
        )
        conn.commit()
        row = conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM schema_migrations").fetchone()
        current = row["v"] if row else 0
        # Cada migração roda numa transação ÚNICA junto com o registro da versão: ou o
        # schema muda E a versão é gravada, ou nada acontece. (Antes, `executescript`
        # comitava antes do INSERT — um crash entre os dois re-executava a migração no
        # boot seguinte e ALTER TABLE estourava "duplicate column", derrubando o app.)
        # O BEGIN explícito é necessário: DDL fora de transação roda em autocommit.
        for version, sql in _MIGRATIONS:
            if version <= current:
                continue
            try:
                conn.execute("BEGIN")
                for stmt in _split_statements(sql):
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (version, _now()),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _setup(self) -> sqlite3.Connection:
        conn = self._open()
        self._migrate(conn)
        return conn

    async def ensure_ready(self) -> None:
        if self._ready:
            return
        async with self._lock:
            if self._ready:
                return
            self._conn = await asyncio.to_thread(self._setup)
            self._ready = True

    # --- operações async (serializadas) ---
    async def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        await self.ensure_ready()
        async with self._lock:
            await asyncio.to_thread(self._exec_commit, sql, tuple(params))

    def _exec_commit(self, sql: str, params: tuple) -> None:
        assert self._conn is not None
        self._conn.execute(sql, params)
        self._conn.commit()

    async def insert(self, sql: str, params: Iterable[Any] = ()) -> int:
        """Executa um INSERT e retorna o id gerado (lastrowid), serializado pelo lock."""
        await self.ensure_ready()
        async with self._lock:
            return await asyncio.to_thread(self._insert_commit, sql, tuple(params))

    def _insert_commit(self, sql: str, params: tuple) -> int:
        assert self._conn is not None
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        return int(cur.lastrowid or 0)

    async def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Optional[dict]:
        await self.ensure_ready()
        async with self._lock:
            row = await asyncio.to_thread(lambda: self._conn.execute(sql, tuple(params)).fetchone())  # type: ignore[union-attr]
        return dict(row) if row else None

    async def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        await self.ensure_ready()
        async with self._lock:
            rows = await asyncio.to_thread(lambda: self._conn.execute(sql, tuple(params)).fetchall())  # type: ignore[union-attr]
        return [dict(r) for r in rows]

    async def backup_now(self, dest_dir: str, retention: int = 14) -> str:
        """Grava um snapshot consistente do banco (API de backup do SQLite) e aplica retenção.

        Um arquivo por dia (`pomar-AAAAMMDD.db`); rodar de novo no mesmo dia substitui o
        snapshot do dia. Mantém os `retention` mais recentes.
        """
        await self.ensure_ready()
        async with self._lock:
            return await asyncio.to_thread(self._backup, dest_dir, retention)

    def _backup(self, dest_dir: str, retention: int) -> str:
        assert self._conn is not None
        os.makedirs(dest_dir, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        dest = os.path.join(dest_dir, f"pomar-{stamp}.db")
        tmp = dest + ".tmp"
        dst = sqlite3.connect(tmp)
        try:
            self._conn.backup(dst)
            dst.close()
            os.replace(tmp, dest)  # troca atômica — nunca deixa snapshot pela metade
        finally:
            try:
                dst.close()
            except sqlite3.ProgrammingError:
                pass  # já fechada
            if os.path.exists(tmp):
                os.remove(tmp)
        snapshots = sorted(
            f for f in os.listdir(dest_dir) if f.startswith("pomar-") and f.endswith(".db")
        )
        for old in snapshots[: max(0, len(snapshots) - max(1, retention))]:
            os.remove(os.path.join(dest_dir, old))
        return dest

    async def close(self) -> None:
        async with self._lock:
            if self._conn is not None:
                await asyncio.to_thread(self._conn.close)
                self._conn = None
                self._ready = False
