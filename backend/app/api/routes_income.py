"""Rotas de renda passiva: renda estimada da carteira e Yield on Cost por ativo."""
from __future__ import annotations

from fastapi import APIRouter

from app.deps import get_brapi, get_cache, get_db, get_ghostfolio
from app.models.analytics import IncomeResponse, YocPoint
from app.repositories import labels_repo, snapshots_repo
from app.services import analytics, market_data
from app.services.portfolio_service import get_enriched_portfolio

router = APIRouter()


async def _portfolio_income_now() -> dict:
    """Renda atual real da carteira. Pode lançar.

    Os números principais usam o DY LÍQUIDO (JCP ×0,85, fallback no bruto quando o
    histórico não distingue o tipo) — é o que cai na conta. O bruto vem junto
    (campos *_gross) para exibição lado a lado.
    """
    overrides = await labels_repo.bucket_overrides(get_db())
    pf = await get_enriched_portfolio(get_ghostfolio(), get_cache(), overrides)
    tickers = [p.ticker for p in pf.positions]
    dy_net: dict[str, float | None] = {}
    dy_gross: dict[str, float | None] = {}
    if tickers:
        assets = await market_data.build_assets(tickers, get_cache(), get_brapi())
        for a in assets:
            dy_gross[a.ticker] = a.fundamentals.dividend_yield
            dy_net[a.ticker] = a.fundamentals.dividend_yield_net or a.fundamentals.dividend_yield
    data = analytics.portfolio_income(pf.positions, dy_net)
    gross = analytics.portfolio_income(pf.positions, dy_gross)
    data["annual_income_gross"] = gross["annual_income"]
    data["monthly_income_gross"] = gross["monthly_income"]
    data["_currency"] = pf.currency
    return data


@router.get("/income", response_model=IncomeResponse)
async def income() -> IncomeResponse:
    """Renda passiva atual estimada da carteira (Σ valor × DY) + Yield on Cost por ativo."""
    try:
        data = await _portfolio_income_now()
    except Exception as exc:  # noqa: BLE001
        return IncomeResponse(warnings=[f"Não consegui calcular a renda: {exc}"])
    currency = data.pop("_currency", "BRL")
    # snapshot mensal oportunista — alimenta a série "bola de neve real" sem cron
    try:
        await snapshots_repo.save_if_new_month(get_db(), data)
    except Exception:  # noqa: BLE001
        pass  # histórico é conveniência; nunca derruba a resposta da renda
    return IncomeResponse(**data, currency=currency)


@router.get("/income/yoc/{ticker}", response_model=list[YocPoint])
async def yoc_history(ticker: str) -> list[YocPoint]:
    """Histórico mensal do Yield on Cost de um ativo (dos snapshots)."""
    rows = await snapshots_repo.yoc_history(get_db(), ticker)
    return [YocPoint(**r) for r in rows]
