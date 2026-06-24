"""Rotas de dados de mercado (inspeção do universo e detalhe de um ativo)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.deps import get_brapi, get_cache, get_db, get_ghostfolio, get_sgs
from app.models.portfolio import Allocations, Portfolio
from app.models.scoring import AssetDetailResponse
from app.repositories import preferences_repo
from app.services import market_data
from app.services.portfolio_service import get_enriched_portfolio
from app.services.scoring import resolve_bazin_target_yield, score_assets
from app.services.universe import build_universe

router = APIRouter()


@router.get("/universe")
async def universe() -> dict:
    try:
        portfolio = await get_enriched_portfolio(get_ghostfolio(), get_cache())
    except Exception:  # noqa: BLE001
        portfolio = Portfolio(
            total_value=0.0, as_of=datetime.now(timezone.utc).isoformat(), allocations=Allocations()
        )
    assets = await build_universe(portfolio, get_cache(), get_brapi())
    return {"count": len(assets), "assets": [a.model_dump() for a in assets]}


@router.get("/asset/{ticker}", response_model=AssetDetailResponse)
async def asset(ticker: str) -> AssetDetailResponse:
    """Detalhe completo do ativo: classe+setor canônicos, fundamentos (incl. LPA/VPA),
    histórico de proventos e a pontuação explicada (métricas, reasons, red flags, selo de risco)."""
    assets = await market_data.build_assets([ticker], get_cache(), get_brapi())
    if not assets or assets[0].price is None:
        raise HTTPException(status_code=404, detail="Ativo não encontrado ou sem dados de mercado.")
    a = assets[0]
    settings = get_settings()
    empty = Portfolio(
        total_value=0.0, as_of=datetime.now(timezone.utc).isoformat(), allocations=Allocations()
    )
    prefs = await preferences_repo.get(get_db(), settings)
    cdi = None
    if (prefs.get("bazin_target_mode") or "fixed_6") == "dynamic_selic":
        try:
            cdi = await get_sgs().cdi_annual()
        except Exception:  # noqa: BLE001
            cdi = None
    bazin_yield = resolve_bazin_target_yield(
        prefs.get("bazin_target_mode"), float(prefs.get("bazin_target_yield") or 0.06), cdi
    )
    scored = score_assets(
        [a], empty, settings.default_targets, settings.default_weights, bazin_target_yield=bazin_yield
    )[0]
    return AssetDetailResponse(asset=a, scored=scored)
