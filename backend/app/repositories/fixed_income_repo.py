"""Repositório do rastreador de renda fixa (contas + lançamentos).

Persiste; o cálculo de saldo/rendimento é puro em `services/fixed_income.py`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.repositories.db import Database
from app.services import fixed_income as fi
from app.util import from_cents, to_cents


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_account(
    db: Database, name: str, institution: Optional[str] = None,
    kind: Optional[str] = None, benchmark: Optional[str] = None,
    counts_in_portfolio: bool = False, purpose: str = "investment",
    liquidity: str = "unknown", redeem_days: Optional[int] = None,
) -> int:
    if purpose == "earmarked" and counts_in_portfolio:
        raise ValueError(fi.EARMARKED_NA_CARTEIRA)
    return await db.insert(
        """INSERT INTO fixed_income_accounts
               (name, institution, kind, benchmark, created_at, archived,
                counts_in_portfolio, purpose, liquidity, redeem_days)
           VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
        (name.strip(), institution, kind, benchmark, _now(),
         int(bool(counts_in_portfolio)), purpose, liquidity, redeem_days),
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
    """PATCH parcial. A combinação proibida é checada contra o estado MESCLADO.

    Validar só o que veio no corpo deixaria passar o caminho mais provável do erro: marcar
    a conta hoje e mudá-la para 'earmarked' amanhã, cada passo válido isoladamente.
    """
    allowed = {
        "name", "institution", "kind", "benchmark", "archived",
        "counts_in_portfolio", "purpose", "liquidity", "redeem_days",
    }
    sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not sets:
        return
    if "counts_in_portfolio" in sets:
        sets["counts_in_portfolio"] = int(bool(sets["counts_in_portfolio"]))
    current = await get_account(db, account_id)
    if current is None:
        raise LookupError("conta não encontrada.")
    merged = {**current, **sets}
    if (merged.get("purpose") or "investment") == "earmarked" and merged.get("counts_in_portfolio"):
        raise ValueError(fi.EARMARKED_NA_CARTEIRA)
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
        "counts_in_portfolio": bool(account.get("counts_in_portfolio")),
        "purpose": account.get("purpose") or "investment",
        "liquidity": account.get("liquidity") or "unknown",
        "redeem_days": account.get("redeem_days"),
        "in_portfolio": fi.counts_in_portfolio(account),
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


async def balances(db: Database, include_archived: bool = False) -> List[Dict[str, Any]]:
    """[{**conta, 'balance': saldo}] — base única das somas, para não repetir a varredura."""
    out: List[Dict[str, Any]] = []
    for acc in await list_accounts(db, include_archived=include_archived):
        entries = await list_entries(db, acc["id"])
        out.append({**acc, "balance": fi.current_balance(entries)})
    return out


def _sum(rows: List[Dict[str, Any]]) -> float:
    """Soma saldos em CENTAVOS inteiros e volta para reais só no fim (ver `util.to_cents`)."""
    return from_cents(sum(to_cents(r["balance"]) for r in rows))


async def total_balance(db: Database) -> float:
    """Tudo que existe na aba Reserva (contas não arquivadas), conte na carteira ou não."""
    return _sum(await balances(db))


async def portfolio_balance(db: Database) -> float:
    """A parte da renda fixa que É patrimônio: marcada e com propósito 'investment'."""
    return _sum([a for a in await balances(db) if fi.counts_in_portfolio(a)])


async def liquid_reserve(db: Database) -> float:
    """Reserva LÍQUIDA — a única que satisfaz o piso.

    Uma LCI travada por dois anos soma normalmente no peso percentual da classe, mas não
    conta aqui. Sem essa separação o app mostraria a reserva como cumprida enquanto o
    dinheiro está preso, que é exatamente a falha que a reserva existe para evitar.
    """
    return _sum([
        a for a in await balances(db)
        if fi.counts_in_portfolio(a) and fi.is_immediately_liquid(a)
    ])
