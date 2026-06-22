"""Rotas da watchlist editável (CRUD + validação por classificação)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.deps import get_cache, get_db
from app.repositories import watchlist_repo
from app.services.classify import classify_ticker
from app.util import normalize_ticker

router = APIRouter()


class WatchlistAdd(BaseModel):
    ticker: str
    note: Optional[str] = None


@router.get("/watchlist")
async def list_watchlist() -> dict:
    db = get_db()
    await watchlist_repo.seed_if_empty(db)
    return {"items": await watchlist_repo.list_all(db)}


@router.post("/watchlist")
async def add_to_watchlist(body: WatchlistAdd) -> dict:
    ticker = normalize_ticker(body.ticker)
    if not ticker:
        raise HTTPException(status_code=422, detail="Ticker inválido.")
    # Valida classificando o ativo (StatusInvest -> watchlist -> heurística).
    asset_class = await classify_ticker(ticker, get_cache())
    await watchlist_repo.add(get_db(), ticker, asset_class, body.note)
    return {"ticker": ticker, "asset_class": asset_class}


@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str) -> dict:
    await watchlist_repo.remove(get_db(), normalize_ticker(ticker))
    return {"ok": True}
