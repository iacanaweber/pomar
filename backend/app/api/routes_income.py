"""Rotas de renda passiva: renda atual da carteira e projeção bola de neve."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.deps import get_brapi, get_cache, get_db, get_ghostfolio
from app.models.analytics import (
    CalendarResponse,
    IncomeGoalResponse,
    IncomeResponse,
    ProjectionRequest,
    ProjectionResponse,
)
from app.providers import statusinvest
from app.repositories import preferences_repo
from app.services import analytics, calendar as calendar_svc, market_data
from app.services.portfolio_service import get_enriched_portfolio

router = APIRouter()


async def _portfolio_income_now() -> dict:
    """Renda atual real da carteira (reusada por /income e /income/goal). Pode lançar."""
    pf = await get_enriched_portfolio(get_ghostfolio(), get_cache())
    tickers = [p.ticker for p in pf.positions]
    dy_by_ticker: dict[str, float | None] = {}
    if tickers:
        assets = await market_data.build_assets(tickers, get_cache(), get_brapi())
        dy_by_ticker = {a.ticker: a.fundamentals.dividend_yield for a in assets}
    data = analytics.portfolio_income(pf.positions, dy_by_ticker)
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
    return IncomeResponse(**data, currency=currency)


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
        )
    return ProjectionResponse(**sb, required_monthly_contribution=required)


@router.get("/income/goal", response_model=IncomeGoalResponse)
async def income_goal() -> IncomeGoalResponse:
    """Objetivo de renda: combina a renda ATUAL real, a meta persistida e o aporte para dizer
    o gap, o % atingido, quanto aportar/mês e em quantos anos você chega lá (Aportador)."""
    settings = get_settings()
    prefs = await preferences_repo.get(get_db(), settings)
    target = float(prefs.get("target_monthly_income") or 0.0)
    horizon = int(prefs.get("target_horizon_years") or 20)
    growth = float(prefs.get("annual_growth") or 0.0)
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

    yld = pyield if pyield and pyield > 0 else 0.06  # fallback p/ projeção quando não há DY
    gap = max(0.0, target - current)
    pct = min(1.0, current / target) if target > 0 else 0.0
    required = (
        analytics.required_monthly_contribution(target, total, yld, growth, horizon)
        if target > 0 else None
    )
    est = (
        analytics.estimated_years_to_goal(target, total, aporte, yld, growth)
        if (target > 0 and aporte > 0) else None
    )
    return IncomeGoalResponse(
        target_monthly_income=round(target, 2),
        current_monthly_income=round(current, 2),
        gap_monthly=round(gap, 2),
        pct_achieved=round(pct, 4),
        horizon_years=horizon,
        portfolio_yield=round(pyield, 4),
        required_monthly_contribution=required,
        estimated_years_to_goal=est,
        warnings=warnings,
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
