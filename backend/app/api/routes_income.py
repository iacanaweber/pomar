"""Rotas de renda passiva: renda atual da carteira e projeção bola de neve."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.deps import get_brapi, get_cache, get_db, get_ghostfolio
from app.models.analytics import (
    AnnouncedPayment,
    AnnouncedResponse,
    CalendarResponse,
    IncomeGoalResponse,
    IncomeResponse,
    ProjectionRequest,
    ProjectionResponse,
    RealizedIncomeResponse,
    SnapshotsResponse,
    YocPoint,
)
from app.providers import statusinvest
from app.repositories import preferences_repo, snapshots_repo
from app.services import analytics, calendar as calendar_svc, market_data
from app.services.portfolio_service import get_enriched_portfolio

router = APIRouter()


async def _portfolio_income_now() -> dict:
    """Renda atual real da carteira (reusada por /income e /income/goal). Pode lançar.

    Os números principais usam o DY LÍQUIDO (JCP ×0,85, fallback no bruto quando o
    histórico não distingue o tipo) — é o que cai na conta e contra o que a meta deve
    ser comparada. O bruto vem junto (campos *_gross) para exibição lado a lado.
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


@router.get("/income/snapshots", response_model=SnapshotsResponse)
async def income_snapshots() -> SnapshotsResponse:
    """Série mensal registrada da carteira (patrimônio, renda, YoC) — bola de neve real."""
    rows = await snapshots_repo.list_all(get_db())
    return SnapshotsResponse(months=rows)


@router.get("/income/yoc/{ticker}", response_model=list[YocPoint])
async def yoc_history(ticker: str) -> list[YocPoint]:
    """Histórico mensal do Yield on Cost de um ativo (dos snapshots)."""
    rows = await snapshots_repo.yoc_history(get_db(), ticker)
    return [YocPoint(**r) for r in rows]


@router.post("/income/projection", response_model=ProjectionResponse)
async def projection(req: ProjectionRequest) -> ProjectionResponse:
    """Projeção bola de neve (e, opcionalmente, o aporte necessário para uma renda-alvo)."""
    sb = analytics.snowball(
        req.current_value,
        req.monthly_contribution,
        req.annual_yield,
        req.annual_growth,
        req.years,
        req.reinvest,
        req.annual_inflation,
    )
    required = None
    if req.target_monthly_income:
        required = analytics.required_monthly_contribution(
            req.target_monthly_income,
            req.current_value,
            req.annual_yield,
            req.annual_growth,
            req.years,
            req.reinvest,
            req.annual_inflation,
        )
    return ProjectionResponse(**sb, required_monthly_contribution=required)


def _milestone_step(current: float) -> float:
    """Granularidade do próximo marco de renda: fina no começo, mais larga depois."""
    if current < 1_000:
        return 100.0
    if current < 5_000:
        return 250.0
    return 500.0


@router.get("/income/goal", response_model=IncomeGoalResponse)
async def income_goal() -> IncomeGoalResponse:
    """Objetivo de renda: combina a renda ATUAL real, a meta persistida e o aporte para dizer
    o gap, o % atingido, quanto aportar/mês e em quantos anos você chega lá (Aportador)."""
    settings = get_settings()
    prefs = await preferences_repo.get(get_db(), settings)
    target = float(prefs.get("target_monthly_income") or 0.0)
    horizon = int(prefs.get("target_horizon_years") or 20)
    growth = float(prefs.get("annual_growth") or 0.0)
    inflation = float(prefs.get("expected_inflation") or 0.0)
    include_rf = bool(prefs.get("include_reserve_income"))
    reserve_target = float(prefs.get("reserve_target") or 0.0)
    aporte = float(prefs.get("aporte_default") or 0.0)
    warnings: list[str] = []
    current, pyield, total = 0.0, 0.0, 0.0
    try:
        data = await _portfolio_income_now()
        current = data["monthly_income"]
        pyield = data["portfolio_yield"]
        total = data["total_value"]
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Não consegui ler a carteira ({exc}); renda atual assumida = 0.")

    # renda estimada da reserva/RF (linha separada; só entra na meta com opt-in)
    reserve_income: float | None = None
    reserve_current = 0.0
    try:
        db = get_db()
        accounts = await fixed_income_repo.list_accounts(db, include_archived=False)
        monthly = 0.0
        for acc in accounts:
            s = await fixed_income_repo.account_summary(db, acc)
            bal = float(s.get("current_balance") or 0.0)
            yld_rf = float(s.get("last_yield_annual") or 0.0)
            reserve_current += bal
            monthly += bal * yld_rf / 12.0
        reserve_income = round(monthly, 2) if accounts else None
    except Exception:  # noqa: BLE001
        pass  # rastreador vazio/indisponível: segue só com RV

    # aporte que efetivamente vai para RV enquanto a reserva não enche (mesmo split do plano)
    from app.services import reserve as reserve_svc

    aporte_rv = aporte
    if aporte > 0 and reserve_target > 0:
        split = reserve_svc.split_aporte_reserva(aporte, total, reserve_current, reserve_target)
        aporte_rv = split["aporte_rv"]
        if split["reserve_directed"] > 0:
            warnings.append(
                f"Do aporte de R$ {aporte:,.0f}, ~R$ {split['reserve_directed']:,.0f} vão para a "
                "reserva enquanto ela não atinge o alvo — a projeção usa só a parte de RV."
            )

    effective_income = current + ((reserve_income or 0.0) if include_rf else 0.0)
    yld = pyield if pyield and pyield > 0 else 0.06  # fallback p/ projeção quando não há DY
    gap = max(0.0, target - effective_income)
    pct = min(1.0, effective_income / target) if target > 0 else 0.0
    required = (
        analytics.required_monthly_contribution(
            target, total, yld, growth, horizon, annual_inflation=inflation
        )
        if target > 0 else None
    )
    est = (
        analytics.estimated_years_to_goal(
            target, total, aporte_rv, yld, growth, annual_inflation=inflation
        )
        if (target > 0 and aporte_rv > 0) else None
    )

    # próximo marco: vitória de curto prazo na jornada de décadas
    step = _milestone_step(effective_income)
    next_ms = (int(effective_income / step) + 1) * step
    ms_gap = round(next_ms - effective_income, 2)
    ms_capital = round(ms_gap * 12 / yld, 2) if yld > 0 else None

    return IncomeGoalResponse(
        target_monthly_income=round(target, 2),
        current_monthly_income=round(current, 2),
        gap_monthly=round(gap, 2),
        pct_achieved=round(pct, 4),
        horizon_years=horizon,
        portfolio_yield=round(pyield, 4),
        required_monthly_contribution=required,
        estimated_years_to_goal=est,
        expected_inflation=inflation,
        reserve_monthly_income=reserve_income,
        include_reserve_income=include_rf,
        aporte_rv_estimated=round(aporte_rv, 2) if aporte > 0 else None,
        next_milestone=next_ms,
        milestone_gap=ms_gap,
        milestone_capital_needed=ms_capital,
        warnings=warnings,
    )


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


@router.get("/income/announced", response_model=AnnouncedResponse)
async def income_announced() -> AnnouncedResponse:
    """Proventos JÁ ANUNCIADOS dos ativos da carteira: 'BBAS3 paga R$ 0,45 dia 12/08 →
    você recebe R$ 213'. Agenda real (data-com e pagamento conhecidos), não estimativa."""
    try:
        pf = await get_enriched_portfolio(get_ghostfolio(), get_cache())
    except Exception as exc:  # noqa: BLE001
        return AnnouncedResponse(warnings=[f"Não consegui ler o Ghostfolio: {exc}"])
    items: list[AnnouncedPayment] = []
    for p in pf.positions:
        try:
            announced = await statusinvest.announced_payments(p.ticker, get_cache(), p.asset_class)
        except Exception:  # noqa: BLE001
            continue
        for a in announced:
            qty = p.quantity
            total = round(a["net_value_per_share"] * qty, 2) if qty else None
            items.append(AnnouncedPayment(**a, quantity=qty, total_net=total))
    items.sort(key=lambda x: (x.payment_date or "9999-12-31"))
    return AnnouncedResponse(
        items=items,
        total_net=round(sum(i.total_net or 0.0 for i in items), 2),
        currency=pf.currency,
    )


@router.get("/income/calendar", response_model=CalendarResponse)
async def income_calendar() -> CalendarResponse:
    """Mapa de proventos mês a mês da carteira atual (estimativa sazonal dos últimos anos)."""
    try:
        pf = await get_enriched_portfolio(get_ghostfolio(), get_cache())
    except Exception as exc:  # noqa: BLE001
        return CalendarResponse(warnings=[f"Não consegui ler o Ghostfolio: {exc}"])
    season: dict[str, dict] = {}
    for p in pf.positions:
        try:
            season[p.ticker] = await statusinvest.monthly_seasonality(
                p.ticker, get_cache(), p.asset_class
            )
        except Exception:  # noqa: BLE001
            continue
    data = calendar_svc.project_calendar(pf.positions, season)
    return CalendarResponse(**data, currency=pf.currency)
