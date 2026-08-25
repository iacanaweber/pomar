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
        # v5: carteira alvo por classe ({"FII": {"AAA11": 0.4, ...}}) — na v6 ela virou o
        # coração do plano. A coluna `focus` (e watchlist.favorite, preferences.strategy,
        # weights_json, max_assets…) ficou órfã: migração SQLite aqui é ADITIVA, nunca
        # dropamos coluna aplicada; elas apenas deixaram de ser lidas e escritas.
        """
        ALTER TABLE preferences ADD COLUMN focus              TEXT NOT NULL DEFAULT 'BALANCE';
        ALTER TABLE preferences ADD COLUMN class_targets_json TEXT;
        """,
    ),
    (
        6,
        # v6: rótulos genéricos por DIMENSÃO, em vez de uma coluna por ideia nova. A
        # dimensão 'bucket' dirige a compra (é a generalização de class_targets_json);
        # 'indexer' e 'geography' descrevem o ativo. Os rótulos EMBUTIDOS não entram aqui:
        # são semeados de forma idempotente no boot (data/labels_seed.py), para acrescentar
        # um builtin novo não exigir migração.
        """
        CREATE TABLE IF NOT EXISTS labels (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            dimension   TEXT NOT NULL,          -- 'indexer' | 'geography' | 'bucket' | futuro
            code        TEXT NOT NULL,          -- 'CDI','SELIC','IPCA','PREFIXADO','LCI','BR','INTL'
            name        TEXT NOT NULL,
            builtin     INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT,
            UNIQUE (dimension, code)
        );

        CREATE TABLE IF NOT EXISTS label_assignments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL,         -- 'ticker' | 'fi_account'
            subject_id   TEXT NOT NULL,         -- ticker normalizado OU id da conta como texto
            label_id     INTEGER NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
            weight       REAL NOT NULL DEFAULT 1.0,   -- exposição parcial (ex.: 60% INTL / 40% BR)
            created_at   TEXT,
            UNIQUE (subject_type, subject_id, label_id)
        );
        CREATE INDEX IF NOT EXISTS idx_label_subject ON label_assignments(subject_type, subject_id);
        """,
    ),
    (
        7,
        # v7: uma conta de renda fixa deixa de ser só "reserva". `counts_in_portfolio=0` por
        # DEFAULT é deliberado: nenhuma conta pré-existente passa a contar no patrimônio (e
        # a mexer nos alvos em R$ das demais classes) sem ação explícita do usuário.
        # `purpose='earmarked'` é dinheiro com destino definido — a conta que provisiona o
        # IR do ano seguinte — e nunca entra na carteira, mesmo marcada.
        """
        ALTER TABLE fixed_income_accounts ADD COLUMN counts_in_portfolio INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE fixed_income_accounts ADD COLUMN purpose             TEXT    NOT NULL DEFAULT 'investment';
        ALTER TABLE fixed_income_accounts ADD COLUMN liquidity           TEXT    NOT NULL DEFAULT 'unknown';
        ALTER TABLE fixed_income_accounts ADD COLUMN redeem_days         INTEGER;
        """,
    ),
    (
        8,
        # v8: o `reserve_target` (fração do patrimônio) é APOSENTADO como percentual e
        # renasce como PISO em R$ dentro da classe RENDA_FIXA:
        #     alvo_RF = max(peso_RF × patrimônio, piso_corrigido)
        # Com `reserve_floor_index='ipca'` o piso é corrigido a partir de
        # `reserve_floor_date` — um piso nominal encolhe sozinho e a tela nunca avisa.
        #
        # `legacy_in_total` é do bloco "ativos fora do alvo" e vem junto por necessidade do
        # motor de migração: `_migrate` compara com MAX(version), então uma versão MENOR
        # acrescentada depois seria pulada em silêncio — as versões precisam nascer em
        # ordem crescente no tempo. DEFAULT 1 reproduz o comportamento de hoje (o legado
        # entra no denominador da comparação atual × alvo).
        """
        ALTER TABLE preferences ADD COLUMN reserve_floor_amount REAL    NOT NULL DEFAULT 0.0;
        ALTER TABLE preferences ADD COLUMN reserve_floor_date   TEXT;
        ALTER TABLE preferences ADD COLUMN reserve_floor_index  TEXT    NOT NULL DEFAULT 'none';
        ALTER TABLE preferences ADD COLUMN legacy_in_total      INTEGER NOT NULL DEFAULT 1;
        """,
    ),
    (
        9,
        # v9: metas das dimensões SECUNDÁRIAS (geografia, tipo de ativo). São informativas e
        # não têm efeito algum sobre a compra: metas vinculantes em duas dimensões
        # independentes formam um sistema sobredeterminado, sem solução para a maioria das
        # combinações. A dimensão que dirige a compra continua sendo só `class_targets_json`.
        """
        ALTER TABLE preferences ADD COLUMN dimension_targets_json TEXT;
        """,
    ),
    (
        10,
        # v10: série SEMANAL do retorno + níveis dos índices de comparação.
        #
        # Tabela separada de `portfolio_snapshots` de propósito: aquela é mensal e serve à
        # bola de neve de RENDA; reaproveitá-la contaminaria a série existente com outra
        # periodicidade e outro significado.
        #
        # `week_of` e `captured_at` são campos distintos porque o container pode estar
        # desligado no domingo: um deles diz a que semana o dado se refere, o outro quando
        # a captura de fato rodou. `late=1` marca a captura fora da janela pretendida, para
        # o gráfico não mentir sobre a data do dado.
        #
        # `flows_json` e `twr_period` são CONGELADOS na captura. Recalcular retroativamente
        # a partir de preço histórico (que muda) ou de lançamento corrigido produziria um
        # gráfico que se reescreve sozinho.
        """
        CREATE TABLE IF NOT EXISTS weekly_snapshots (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            week_of        TEXT NOT NULL UNIQUE,      -- 'yyyy-Www' (ISO)
            week_end       TEXT NOT NULL,             -- domingo a que a semana se refere
            captured_at    TEXT NOT NULL,
            late           INTEGER NOT NULL DEFAULT 0,
            total_value    REAL NOT NULL,
            rv_value       REAL,
            rf_value       REAL,
            flow_net       REAL NOT NULL DEFAULT 0,
            flow_weighted  REAL NOT NULL DEFAULT 0,
            twr_period     REAL,
            twr_cumulative REAL,
            flows_json     TEXT,
            detail_json    TEXT
        );

        CREATE TABLE IF NOT EXISTS benchmark_series (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT NOT NULL,
            obs_date    TEXT NOT NULL,
            level       REAL NOT NULL,
            source      TEXT,
            captured_at TEXT,
            UNIQUE (code, obs_date)
        );
        CREATE INDEX IF NOT EXISTS idx_bench_code_date ON benchmark_series(code, obs_date);
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
