"""Rotas de renda passiva: renda atual da carteira e projeção bola de neve."""
from __future__ import annotations

from fastapi import APIRouter

from app.deps import get_brapi, get_cache, get_ghostfolio
from app.models.analytics import IncomeResponse, ProjectionRequest, ProjectionResponse
from app.services import analytics, market_data
from app.services.portfolio_service import get_enriched_portfolio

router = APIRouter()


@router.get("/income", response_model=IncomeResponse)
async def income() -> IncomeResponse:
    """Renda passiva atual estimada da carteira (Σ valor × DY), com decomposição por ativo."""
    warnings: list[str] = []
    try:
        pf = await get_enriched_portfolio(get_ghostfolio(), get_cache())
    except Exception as exc:  # noqa: BLE001
        return IncomeResponse(warnings=[f"Não consegui ler o Ghostfolio: {exc}"])

    tickers = [p.ticker for p in pf.positions]
    dy_by_ticker: dict[str, float | None] = {}
    if tickers:
        try:
            assets = await market_data.build_assets(tickers, get_cache(), get_brapi())
            dy_by_ticker = {a.ticker: a.fundamentals.dividend_yield for a in assets}
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Falha ao buscar dados de mercado: {exc}")

    data = analytics.portfolio_income(pf.positions, dy_by_ticker)
    return IncomeResponse(**data, currency=pf.currency, warnings=warnings)


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
