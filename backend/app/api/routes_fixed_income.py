"""Rotas do rastreador de renda fixa: contas, lançamentos e rendimento (% do CDI)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.deps import get_db, get_sgs
from app.models.fixed_income import (
    AccountIn,
    AccountSummary,
    EntryIn,
    EntryOut,
    FixedIncomeSummary,
)
from app.repositories import fixed_income_repo as repo
from app.services import fixed_income as fi

router = APIRouter()


async def _summary_with_cdi(account: dict, cdi: float | None) -> AccountSummary:
    s = await repo.account_summary(get_db(), account)
    s["pct_of_cdi"] = fi.pct_of_cdi(s.get("last_yield_annual"), cdi)
    return AccountSummary(**s)


@router.get("/fixed-income/summary", response_model=FixedIncomeSummary)
async def fixed_income_summary() -> FixedIncomeSummary:
    db = get_db()
    cdi = await get_sgs().cdi_annual()
    accounts = await repo.list_accounts(db, include_archived=False)
    summaries = [await _summary_with_cdi(a, cdi) for a in accounts]
    total = round(sum(s.current_balance for s in summaries), 2)
    return FixedIncomeSummary(accounts=summaries, total_balance=total, cdi_annual=cdi)


@router.post("/fixed-income/accounts", response_model=AccountSummary)
async def create_account(body: AccountIn) -> AccountSummary:
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Nome da conta é obrigatório.")
    db = get_db()
    acc_id = await repo.create_account(db, body.name, body.institution, body.kind, body.benchmark)
    acc = await repo.get_account(db, acc_id)
    return await _summary_with_cdi(acc, await get_sgs().cdi_annual())


@router.patch("/fixed-income/accounts/{account_id}", response_model=AccountSummary)
async def update_account(account_id: int, body: AccountIn) -> AccountSummary:
    db = get_db()
    if not await repo.get_account(db, account_id):
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    await repo.update_account(
        db, account_id, name=body.name, institution=body.institution,
        kind=body.kind, benchmark=body.benchmark,
    )
    return await _summary_with_cdi(await repo.get_account(db, account_id), await get_sgs().cdi_annual())


@router.delete("/fixed-income/accounts/{account_id}")
async def archive_account(account_id: int) -> dict:
    db = get_db()
    if not await repo.get_account(db, account_id):
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    await repo.update_account(db, account_id, archived=1)
    return {"ok": True, "archived": True}


@router.get("/fixed-income/accounts/{account_id}/entries")
async def list_entries(account_id: int) -> dict:
    db = get_db()
    if not await repo.get_account(db, account_id):
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    rows = await repo.list_entries(db, account_id)
    return {"items": [EntryOut(**r).model_dump() for r in rows]}


@router.post("/fixed-income/accounts/{account_id}/entries", response_model=AccountSummary)
async def add_entry(account_id: int, body: EntryIn) -> AccountSummary:
    db = get_db()
    if not await repo.get_account(db, account_id):
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    await repo.add_entry(db, account_id, body.kind, body.amount, body.entry_date, body.note)
    # devolve o resumo já com o rendimento recalculado (relevante após uma atualização de saldo)
    return await _summary_with_cdi(await repo.get_account(db, account_id), await get_sgs().cdi_annual())
