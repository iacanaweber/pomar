"""Repositório do rastreador de renda fixa (contas + lançamentos).

Persiste; o cálculo de saldo/rendimento é puro em `services/fixed_income.py`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.repositories.db import Database
from app.services import fixed_income as fi


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_account(
    db: Database, name: str, institution: Optional[str] = None,
    kind: Optional[str] = None, benchmark: Optional[str] = None,
) -> int:
    return await db.insert(
        """INSERT INTO fixed_income_accounts (name, institution, kind, benchmark, created_at, archived)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (name.strip(), institution, kind, benchmark, _now()),
    )


async def list_accounts(db: Database, include_archived: bool = False) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM fixed_income_accounts"
    if not include_archived:
        sql += " WHERE archived = 0"
    sql += " ORDER BY name"
    return await db.fetchall(sql)


async def get_account(db: Database, account_id: int) -> Optional[Dict[str, Any]]:
    return await db.fetchone("SELECT * FROM fixed_income_accounts WHERE id = ?", (account_id,))


async def update_account(db: Database, account_id: int, **fields: Any) -> None:
    allowed = {"name", "institution", "kind", "benchmark", "archived"}
    sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not sets:
        return
    cols = ", ".join(f"{k} = ?" for k in sets)
    await db.execute(
        f"UPDATE fixed_income_accounts SET {cols} WHERE id = ?", (*sets.values(), account_id)
    )


async def add_entry(
    db: Database, account_id: int, kind: str, amount: float,
    entry_date: Optional[str] = None, note: Optional[str] = None,
) -> int:
    # default = data LOCAL do Brasil: com UTC, um lançamento depois das ~21h ganhava a
    # data de amanhã e distorcia a contagem de dias úteis do rendimento.
    from zoneinfo import ZoneInfo

    entry_date = (entry_date or datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat())[:10]
    return await db.insert(
        """INSERT INTO fixed_income_entries (account_id, kind, amount, entry_date, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (account_id, kind, float(amount), entry_date, note, _now()),
    )


async def list_entries(db: Database, account_id: int) -> List[Dict[str, Any]]:
    return await db.fetchall(
        "SELECT * FROM fixed_income_entries WHERE account_id = ? ORDER BY entry_date DESC, id DESC",
        (account_id,),
    )


async def get_entry(db: Database, entry_id: int) -> Optional[Dict[str, Any]]:
    return await db.fetchone("SELECT * FROM fixed_income_entries WHERE id = ?", (entry_id,))


async def delete_entry(db: Database, entry_id: int) -> None:
    await db.execute("DELETE FROM fixed_income_entries WHERE id = ?", (entry_id,))


async def account_summary(db: Database, account: Dict[str, Any]) -> Dict[str, Any]:
    """Monta o resumo de uma conta (saldo atual + rendimento do histórico e da última janela)."""
    entries = await list_entries(db, account["id"])
    hy = fi.history_yield(entries)
    ly = fi.last_yield(entries)
    return {
        "id": account["id"],
        "name": account["name"],
        "institution": account.get("institution"),
        "kind": account.get("kind"),
        "benchmark": account.get("benchmark"),
        "archived": bool(account.get("archived")),
        "current_balance": fi.current_balance(entries),
        "history_yield_annual": hy["annualized"] if hy else None,
        "history_yield_gain": hy["gain"] if hy else None,
        "history_yield_from": hy["from_date"] if hy else None,
        "history_yield_to": hy["to_date"] if hy else None,
        "history_yield_business_days": hy["business_days"] if hy else None,
        "last_yield_annual": ly["annualized"] if ly else None,
        "last_yield_gain": ly["gain"] if ly else None,
        "last_yield_from": ly["from_date"] if ly else None,
        "last_yield_to": ly["to_date"] if ly else None,
        "last_yield_business_days": ly["business_days"] if ly else None,
    }


async def total_balance(db: Database) -> float:
    """Soma do saldo atual de todas as contas não arquivadas (= reserva atual)."""
    total = 0.0
    for acc in await list_accounts(db, include_archived=False):
        entries = await list_entries(db, acc["id"])
        total += fi.current_balance(entries)
    return round(total, 2)
