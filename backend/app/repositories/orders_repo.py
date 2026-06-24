"""Repositório de ordens executadas ('já comprei') — usa a tabela executed_orders."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.repositories.db import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def record_order(
    db: Database, ticker: str, asset_class: Optional[str], shares: int, price: float,
    fees: float = 0.0, executed_at: Optional[str] = None, note: Optional[str] = None,
    plan_id: Optional[int] = None,
) -> int:
    return await db.insert(
        """INSERT INTO executed_orders (plan_id, ticker, asset_class, shares, price, fees, executed_at, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (plan_id, ticker.strip().upper(), asset_class, int(shares), float(price),
         float(fees or 0.0), (executed_at or _now()), note),
    )


async def get_order(db: Database, order_id: int) -> Optional[Dict[str, Any]]:
    return await db.fetchone("SELECT * FROM executed_orders WHERE id = ?", (order_id,))


async def list_orders(db: Database, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
    return await db.fetchall(
        "SELECT * FROM executed_orders ORDER BY executed_at DESC, id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )


async def delete_order(db: Database, order_id: int) -> None:
    await db.execute("DELETE FROM executed_orders WHERE id = ?", (order_id,))


async def total_invested(db: Database) -> float:
    rows = await db.fetchall("SELECT shares, price, fees FROM executed_orders")
    return round(sum(r["shares"] * r["price"] + (r["fees"] or 0.0) for r in rows), 2)


async def realized_cost_by_ticker(db: Database) -> Dict[str, float]:
    """Custo realizado por ticker (Σ cotas×preço + custos) — fallback p/ Yield on Cost."""
    rows = await db.fetchall(
        "SELECT ticker, SUM(shares * price + COALESCE(fees, 0)) AS cost FROM executed_orders GROUP BY ticker"
    )
    return {r["ticker"]: round(r["cost"] or 0.0, 2) for r in rows}
