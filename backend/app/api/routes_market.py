"""Rotas de dados de mercado (inspeção do universo e detalhe de um ativo)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.deps import get_brapi, get_cache, get_ghostfolio
from app.models.portfolio import Allocations, Portfolio
from app.services.universe import build_universe

router = APIRouter()


@router.get("/universe")
async def universe() -> dict:
    try:
        portfolio = await get_ghostfolio().get_portfolio()
    except Exception:  # noqa: BLE001
        portfolio = Portfolio(
            total_value=0.0, as_of=datetime.now(timezone.utc).isoformat(), allocations=Allocations()
        )
    assets = await build_universe(portfolio, get_cache(), get_brapi())
    return {"count": len(assets), "assets": [a.model_dump() for a in assets]}


@router.get("/asset/{ticker}")
async def asset(ticker: str) -> dict:
    assets = await get_brapi().get_assets([ticker])
    if not assets:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    return assets[0].model_dump()
