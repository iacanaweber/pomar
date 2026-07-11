"""Repositório da watchlist editável (substitui a lista hardcoded em data/watchlist.py).

Semeada a partir da watchlist curada na primeira execução; depois é editável pela UI.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.repositories.db import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def list_all(db: Database) -> List[Dict[str, Any]]:
    return await db.fetchall("SELECT * FROM watchlist ORDER BY asset_class, ticker")


async def tickers(db: Database) -> List[str]:
    rows = await db.fetchall("SELECT ticker FROM watchlist WHERE valid = 1 ORDER BY ticker")
    return [r["ticker"] for r in rows]


async def count(db: Database) -> int:
    row = await db.fetchone("SELECT COUNT(*) AS n FROM watchlist")
    return int(row["n"]) if row else 0


async def add(
    db: Database, ticker: str, asset_class: str = "STOCK", note: str | None = None, valid: bool = True
) -> None:
    ticker = ticker.strip().upper()
    await db.execute(
        """
        INSERT INTO watchlist (ticker, asset_class, note, added_at, last_validated_at, valid)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            asset_class=excluded.asset_class,
            note=excluded.note,
            last_validated_at=excluded.last_validated_at,
            valid=excluded.valid
        """,
        (ticker, asset_class, note, _now(), _now() if valid else None, 1 if valid else 0),
    )


async def remove(db: Database, ticker: str) -> None:
    await db.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.strip().upper(),))


async def set_favorite(db: Database, ticker: str, favorite: bool) -> bool:
    """Marca/desmarca um ⭐. Retorna False se o ticker não está na watchlist."""
    ticker = ticker.strip().upper()
    row = await db.fetchone("SELECT ticker FROM watchlist WHERE ticker = ?", (ticker,))
    if not row:
        return False
    await db.execute(
        "UPDATE watchlist SET favorite = ? WHERE ticker = ?", (1 if favorite else 0, ticker)
    )
    return True


async def favorites(db: Database) -> Dict[str, List[str]]:
    """Favoritos válidos agrupados por classe: {'FII': ['BTGL11', ...], ...}."""
    rows = await db.fetchall(
        "SELECT ticker, asset_class FROM watchlist WHERE favorite = 1 AND valid = 1 ORDER BY ticker"
    )
    out: Dict[str, List[str]] = {}
    for r in rows:
        out.setdefault(r["asset_class"] or "STOCK", []).append(r["ticker"])
    return out


async def seed_if_empty(db: Database) -> int:
    """Popula a watchlist com a lista curada se ela estiver vazia. Retorna quantos inseriu."""
    if await count(db) > 0:
        return 0
    from app.data.watchlist import CLASS_BY_TICKER

    inserted = 0
    for ticker, asset_class in CLASS_BY_TICKER.items():
        await add(db, ticker, asset_class)
        inserted += 1
    return inserted
