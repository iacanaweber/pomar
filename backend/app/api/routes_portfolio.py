"""Rota da carteira atual (Ghostfolio)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.deps import get_ghostfolio
from app.models.portfolio import Portfolio

router = APIRouter()


@router.get("/portfolio", response_model=Portfolio)
async def portfolio() -> Portfolio:
    try:
        return await get_ghostfolio().get_portfolio()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Não consegui ler o Ghostfolio: {exc}. Verifique GHOSTFOLIO_URL e o token.",
        )
