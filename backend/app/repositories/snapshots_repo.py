"""Snapshots mensais da carteira — a série histórica da bola de neve REAL.

Um registro por mês ('yyyy-mm'), gravado oportunisticamente no primeiro acesso à renda
do mês (sem cron — coerente com um app pull-based de uso pessoal). Guarda os agregados
e o detalhe por ativo (YoC, renda) em JSON, para o histórico de YoC na página do ativo.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.repositories.db import Database


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def save_if_new_month(db: Database, income: Dict[str, Any]) -> bool:
    """Grava o snapshot do mês corrente se ainda não existir. Retorna True se gravou.

    `income` é o dict do analytics.portfolio_income (números líquidos).
    """
    total_value = float(income.get("total_value") or 0.0)
    if total_value <= 0:
        return False  # carteira vazia/indisponível não vira histórico
    month = _current_month()
    exists = await db.fetchone("SELECT 1 FROM portfolio_snapshots WHERE month = ?", (month,))
    if exists:
        return False
    by_asset = {
        a["ticker"]: {"yoc": a.get("yield_on_cost"), "annual_income": a.get("annual_income")}
        for a in income.get("by_asset", [])
    }
    await db.execute(
        """
        INSERT INTO portfolio_snapshots
            (month, created_at, total_value, annual_income, monthly_income,
             portfolio_yield, yield_on_cost, snapshot_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            month,
            datetime.now(timezone.utc).isoformat(),
            round(total_value, 2),
            income.get("annual_income"),
            income.get("monthly_income"),
            income.get("portfolio_yield"),
            income.get("yield_on_cost"),
            json.dumps(by_asset),
        ),
    )
    return True


async def list_all(db: Database) -> List[Dict[str, Any]]:
    rows = await db.fetchall(
        """
        SELECT month, total_value, annual_income, monthly_income, portfolio_yield, yield_on_cost
        FROM portfolio_snapshots ORDER BY month
        """
    )
    return rows


async def yoc_history(db: Database, ticker: str) -> List[Dict[str, Optional[float]]]:
    """Série {month, yoc} de um ativo, extraída do snapshot_json de cada mês."""
    rows = await db.fetchall(
        "SELECT month, snapshot_json FROM portfolio_snapshots ORDER BY month"
    )
    out: List[Dict[str, Optional[float]]] = []
    for r in rows:
        try:
            detail = json.loads(r["snapshot_json"] or "{}")
        except (TypeError, ValueError):
            continue
        info = detail.get(ticker.upper())
        if info is not None:
            out.append({"month": r["month"], "yoc": info.get("yoc")})
    return out
