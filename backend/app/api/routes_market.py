"""Rotas de dados de mercado (inspeção do universo e detalhe de um ativo)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.deps import get_brapi, get_cache, get_db, get_ghostfolio, get_sgs
from app.models.plan import AssetDetailResponse
from app.models.portfolio import Allocations, Portfolio
from app.repositories import labels_repo, preferences_repo
from app.services import market_data
from app.services.analysis import analyze_asset, resolve_bazin_target_yield
from app.services.portfolio_service import get_enriched_portfolio
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
    histórico de proventos e a leitura factual (preço-teto, consistência, red flags)."""
    # A cesta escolhida à mão vence a classificação automática — sem passar os
    # overrides, esta tela mostrava "Automática (ETF)" logo depois de o usuário ter
    # marcado renda fixa NELA MESMA.
    overrides = await labels_repo.bucket_overrides(get_db())
    assets = await market_data.build_assets(
        [ticker], get_cache(), get_brapi(), bucket_overrides=overrides
    )
    if not assets or assets[0].price is None:
        raise HTTPException(status_code=404, detail="Ativo não encontrado ou sem dados de mercado.")
    a = assets[0]
    prefs = await preferences_repo.get(get_db(), get_settings())
    cdi = None
    if (prefs.get("bazin_target_mode") or "fixed_6") == "dynamic_selic":
        try:
            cdi = await get_sgs().cdi_annual()
        except Exception:  # noqa: BLE001
            cdi = None
    bazin_yield = resolve_bazin_target_yield(
        prefs.get("bazin_target_mode"), float(prefs.get("bazin_target_yield") or 0.06), cdi
    )
    return AssetDetailResponse(asset=a, analysis=analyze_asset(a, bazin_yield))
