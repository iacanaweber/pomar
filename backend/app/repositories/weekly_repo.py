"""Série semanal do retorno + níveis dos índices de comparação.

Separado de `snapshots_repo` (mensal, bola de neve de renda) porque é outra periodicidade
e outro significado. O que é gravado aqui é CONGELADO: recalcular a partir de preço
histórico — que muda — produziria um gráfico que se reescreve sozinho.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from app.repositories.db import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- snapshots semanais ---

async def get_week(db: Database, week_of: str) -> Optional[Dict[str, Any]]:
    return await db.fetchone("SELECT * FROM weekly_snapshots WHERE week_of = ?", (week_of,))


async def last_week(db: Database) -> Optional[Dict[str, Any]]:
    return await db.fetchone(
        "SELECT * FROM weekly_snapshots ORDER BY week_end DESC LIMIT 1"
    )


async def list_weeks(db: Database, limit: int = 520) -> List[Dict[str, Any]]:
    return await db.fetchall(
        "SELECT * FROM weekly_snapshots ORDER BY week_end LIMIT ?", (limit,)
    )


async def save_week(
    db: Database,
    *,
    week_of: str,
    week_end: str,
    late: bool,
    total_value: float,
    rv_value: float,
    rf_value: float,
    flow_net: float,
    flow_weighted: float,
    twr_period: Optional[float],
    twr_cumulative: Optional[float],
    flows: Sequence[Dict[str, Any]],
    detail: Optional[Dict[str, Any]] = None,
) -> bool:
    """Grava a semana. `INSERT OR IGNORE`: reexecutar a captura não sobrescreve o que já
    está lá — o congelamento é o ponto. Devolve True se gravou agora."""
    if await get_week(db, week_of):
        return False
    await db.insert(
        """
        INSERT INTO weekly_snapshots
            (week_of, week_end, captured_at, late, total_value, rv_value, rf_value,
             flow_net, flow_weighted, twr_period, twr_cumulative, flows_json, detail_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            week_of, week_end, _now(), int(bool(late)),
            round(total_value, 2), round(rv_value, 2), round(rf_value, 2),
            round(flow_net, 2), round(flow_weighted, 2),
            twr_period, twr_cumulative,
            json.dumps(list(flows)), json.dumps(detail or {}),
        ),
    )
    return True


# --- séries de benchmark ---

async def save_level(
    db: Database, code: str, obs_date: str, level: float, source: Optional[str] = None
) -> None:
    """Grava o NÍVEL do índice na data. Nível e não variação: guardando o nível dá para
    recalcular o retorno de qualquer janela depois; guardando a variação, não."""
    await db.execute(
        """INSERT INTO benchmark_series (code, obs_date, level, source, captured_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(code, obs_date) DO UPDATE SET
             level = excluded.level, source = excluded.source""",
        (code, obs_date[:10], float(level), source, _now()),
    )


async def levels(db: Database, code: str) -> List[Dict[str, Any]]:
    return await db.fetchall(
        "SELECT obs_date, level FROM benchmark_series WHERE code = ? ORDER BY obs_date",
        (code,),
    )


async def all_levels(db: Database) -> Dict[str, List[Dict[str, Any]]]:
    rows = await db.fetchall(
        "SELECT code, obs_date, level FROM benchmark_series ORDER BY code, obs_date"
    )
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["code"], []).append({"obs_date": r["obs_date"], "level": r["level"]})
    return out


async def codes(db: Database) -> List[str]:
    rows = await db.fetchall("SELECT DISTINCT code FROM benchmark_series ORDER BY code")
    return [r["code"] for r in rows]
