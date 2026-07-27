"""Rotas de renda passiva: renda estimada da carteira, renda realizada e Yield on Cost."""
from __future__ import annotations

from fastapi import APIRouter

from app.deps import get_brapi, get_cache, get_db, get_ghostfolio
from app.models.analytics import IncomeResponse, RealizedIncomeResponse, YocPoint
from app.repositories import snapshots_repo
from app.services import analytics, market_data
from app.services.portfolio_service import get_enriched_portfolio

router = APIRouter()


async def _portfolio_income_now() -> dict:
    """Renda atual real da carteira. Pode lançar.

    Os números principais usam o DY LÍQUIDO (JCP ×0,85, fallback no bruto quando o
    histórico não distingue o tipo) — é o que cai na conta. O bruto vem junto
    (campos *_gross) para exibição lado a lado.
    """
    pf = await get_enriched_portfolio(get_ghostfolio(), get_cache())
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


_REALIZED_TTL = 900  # 15 min — proventos recebidos mudam poucas vezes ao dia


@router.get("/income/realized", response_model=RealizedIncomeResponse)
async def income_realized() -> RealizedIncomeResponse:
    """Renda REALIZADA mês a mês — os dividendos que de fato caíram na conta, lidos das
    atividades do Ghostfolio (você já os registra lá; nada precisa ser redigitado)."""
    cache = get_cache()
    cached = cache.get("gf:realized")
    if cached is not None:
        return RealizedIncomeResponse(**cached)
    try:
        gf = get_ghostfolio()
        months = await gf.get_dividends_by_month()
        activities = await gf.get_dividend_activities()
    except Exception as exc:  # noqa: BLE001
        stale = cache.get_stale("gf:realized")
        if stale is not None:
            resp = RealizedIncomeResponse(**stale)
            resp.warnings = [*resp.warnings, f"Ghostfolio indisponível ({exc}); dados em cache."]
            return resp
        return RealizedIncomeResponse(
            warnings=[f"Não consegui ler os proventos recebidos do Ghostfolio: {exc}"]
        )

    from datetime import date, timedelta

    today = date.today()
    cutoff_12m = (today - timedelta(days=365)).isoformat()[:7]
    cutoff_30d = (today - timedelta(days=30)).isoformat()
    total_12m = round(sum(m["total"] for m in months if m["month"] > cutoff_12m), 2)
    by_asset: dict[str, float] = {}
    for a in activities:
        if a["date"] > cutoff_12m + "-01":
            by_asset[a["ticker"]] = by_asset.get(a["ticker"], 0.0) + a["value"]
    data = {
        "months": months[-24:],
        "total_12m": total_12m,
        "monthly_avg_12m": round(total_12m / 12, 2),
        "by_asset_12m": [
            {"ticker": t, "total": round(v, 2)}
            for t, v in sorted(by_asset.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "last_payments": list(reversed(activities[-10:])),
        "total_30d": round(sum(a["value"] for a in activities if a["date"] >= cutoff_30d), 2),
        "warnings": [],
    }
    cache.set("gf:realized", data, _REALIZED_TTL)
    return RealizedIncomeResponse(**data)


