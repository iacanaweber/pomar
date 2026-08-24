"""Rotas do rastreador de renda fixa: contas, lançamentos e rendimento (% do CDI)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.data.labels_seed import NO_INDEXER_CODE, NO_INDEXER_NAME
from app.deps import get_cache, get_db, get_ghostfolio, get_sgs
from app.models.fixed_income import (
    AccountIn,
    AccountPatch,
    AccountSummary,
    EntryIn,
    EntryOut,
    FixedIncomeSummary,
    FloorStatus,
    IndexersResponse,
    IndexerSlice,
)
from app.models.plan import RENDA_FIXA
from app.repositories import fixed_income_repo as repo
from app.repositories import labels_repo, preferences_repo
from app.services import fixed_income as fi
from app.services import indexers as indexers_svc
from app.services.portfolio_service import get_enriched_portfolio
from app.services.reserve_service import resolve_floor
from app.util import from_cents, to_cents

router = APIRouter()


async def _summary_with_cdi(account: dict, cdi: float | None) -> AccountSummary:
    s = await repo.account_summary(get_db(), account)
    # compara com o CDI o rendimento do HISTÓRICO, não o da última janela: é o único dos dois
    # que não muda de valor conforme o usuário decide quando atualizar o saldo.
    s["pct_of_cdi"] = fi.pct_of_cdi(s.get("history_yield_annual"), cdi)
    return AccountSummary(**s)


@router.get("/fixed-income/summary", response_model=FixedIncomeSummary)
async def fixed_income_summary(include_archived: bool = False) -> FixedIncomeSummary:
    db = get_db()
    cdi = await get_sgs().cdi_annual()
    accounts = await repo.list_accounts(db, include_archived=include_archived)
    summaries = [await _summary_with_cdi(a, cdi) for a in accounts]
    # os totais contam só as contas ATIVAS, mesmo quando as arquivadas são listadas
    ativas = [s for s in summaries if not s.archived]

    def soma(contas) -> int:
        """Em centavos inteiros — o total precisa bater com a soma do que a tela mostra."""
        return sum(to_cents(s.current_balance) for s in contas)

    total = soma(ativas)
    na_carteira = soma([s for s in ativas if s.in_portfolio])
    liquida = soma([s for s in ativas if s.in_portfolio and s.liquidity == "immediate"])

    prefs = await preferences_repo.get(db, get_settings())
    piso = await resolve_floor(prefs, from_cents(liquida), get_sgs())
    return FixedIncomeSummary(
        accounts=summaries,
        total_balance=from_cents(total),
        portfolio_balance=from_cents(na_carteira),
        liquid_balance=from_cents(liquida),
        excluded_balance=from_cents(total - na_carteira),
        floor=FloorStatus(**piso) if piso["floor_nominal"] > 0 else None,
        cdi_annual=cdi,
    )


@router.get("/fixed-income/indexers", response_model=IndexersResponse)
async def indexers() -> IndexersResponse:
    """Composição da classe RENDA_FIXA por tag de indexador — atual × alvo.

    Junta os dois lados da classe: os saldos das contas e as posições de renda variável que
    o usuário atribuiu ao bucket `RENDA_FIXA` (um IMAB11 pesa na cesta ao lado de um CDB).
    Ghostfolio fora do ar não derruba a resposta: a parte de renda fixa continua correta e
    a resposta diz o que ficou de fora.
    """
    db = get_db()
    settings = get_settings()
    warnings: list[str] = []

    contas = [a for a in await repo.balances(db) if fi.counts_in_portfolio(a)]
    rotulos_conta = await labels_repo.assignments_by_subject(db, "indexer", "fi_account")
    rotulos_ticker = await labels_repo.assignments_by_subject(db, "indexer", "ticker")

    posicoes: list[dict] = []
    try:
        overrides = await labels_repo.bucket_overrides(db)
        pf = await get_enriched_portfolio(get_ghostfolio(), get_cache(), overrides)
        posicoes = [
            {"ticker": p.ticker, "value": p.value}
            for p in pf.positions
            if p.asset_class == RENDA_FIXA
        ]
    except Exception as exc:  # noqa: BLE001
        warnings.append(
            f"Não consegui ler a carteira ({exc}); a composição mostra só as contas de renda fixa."
        )

    valores = indexers_svc.value_by_indexer(contas, rotulos_conta, posicoes, rotulos_ticker)
    prefs = await preferences_repo.get(db, settings)
    alvos = (prefs.get("class_targets") or {}).get(RENDA_FIXA) or {}

    nomes = {r["code"]: r["name"] for r in await labels_repo.list_labels(db, "indexer")}
    nomes[NO_INDEXER_CODE] = NO_INDEXER_NAME

    total = from_cents(sum(to_cents(v) for v in valores.values()))
    items = [
        IndexerSlice(
            code=code,
            name=nomes.get(code, code),
            value=valores.get(code, 0.0),
            current_pct=round(valores.get(code, 0.0) / total, 6) if total > 0 else 0.0,
            target_pct=round(float(alvos.get(code, 0.0)), 6),
            gap=from_cents(to_cents(float(alvos.get(code, 0.0)) * total) - to_cents(valores.get(code, 0.0))),
        )
        # tags com valor OU com alvo: uma tag com peso e nenhuma conta é um alvo ainda não
        # aplicado, e some da tela se filtrarmos só por valor
        for code in sorted(set(valores) | set(alvos))
    ]
    if NO_INDEXER_CODE in valores:
        warnings.append(
            "Há saldo em contas que contam na carteira e não têm indexador — sem a tag, "
            "esse dinheiro não entra em nenhum item da cesta de renda fixa."
        )
    return IndexersResponse(items=items, total=total, warnings=warnings)


@router.post("/fixed-income/accounts", response_model=AccountSummary)
async def create_account(body: AccountIn) -> AccountSummary:
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Nome da conta é obrigatório.")
    db = get_db()
    try:
        acc_id = await repo.create_account(
            db, body.name, body.institution, body.kind, body.benchmark,
            counts_in_portfolio=body.counts_in_portfolio, purpose=body.purpose,
            liquidity=body.liquidity, redeem_days=body.redeem_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    acc = await repo.get_account(db, acc_id)
    return await _summary_with_cdi(acc, await get_sgs().cdi_annual())


@router.patch("/fixed-income/accounts/{account_id}", response_model=AccountSummary)
async def update_account(account_id: int, body: AccountPatch) -> AccountSummary:
    db = get_db()
    if not await repo.get_account(db, account_id):
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "archived" in fields:
        fields["archived"] = int(fields["archived"])
    if "name" in fields and not str(fields["name"]).strip():
        raise HTTPException(status_code=422, detail="Nome da conta não pode ficar vazio.")
    if fields:
        try:
            await repo.update_account(db, account_id, **fields)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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


@router.delete("/fixed-income/accounts/{account_id}/entries/{entry_id}")
async def delete_entry(account_id: int, entry_id: int) -> dict:
    db = get_db()
    entry = await repo.get_entry(db, entry_id)
    if not entry or entry["account_id"] != account_id:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")
    await repo.delete_entry(db, entry_id)
    return {"ok": True}


@router.post("/fixed-income/accounts/{account_id}/entries", response_model=AccountSummary)
async def add_entry(account_id: int, body: EntryIn) -> AccountSummary:
    db = get_db()
    if not await repo.get_account(db, account_id):
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    await repo.add_entry(db, account_id, body.kind, body.amount, body.entry_date, body.note)
    # devolve o resumo já com o rendimento recalculado (relevante após uma atualização de saldo)
    return await _summary_with_cdi(await repo.get_account(db, account_id), await get_sgs().cdi_annual())
