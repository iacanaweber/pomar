"""Rotas da watchlist editável (CRUD + validação por classificação + radar de teto)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.deps import get_brapi, get_cache, get_db, get_sgs
from app.repositories import preferences_repo, watchlist_repo
from app.services import market_data
from app.services.analysis import (
    _bazin_ceiling_price,
    _bazin_margin,
    resolve_bazin_target_yield,
)
from app.services.classify import classify_ticker
from app.util import normalize_ticker

router = APIRouter()


class WatchlistAdd(BaseModel):
    ticker: str
    note: Optional[str] = None


class RadarItem(BaseModel):
    """Linha do radar: os dados de DECISÃO de cada ativo observado."""

    ticker: str
    asset_class: str = "STOCK"
    price: Optional[float] = None
    dividend_yield: Optional[float] = None
    dividend_yield_net: Optional[float] = None
    ceiling_price: Optional[float] = None
    margin: Optional[float] = Field(None, description="(teto − preço) ÷ teto; positivo = desconto.")
    below_ceiling: Optional[bool] = None
    in_portfolio: bool = False


class RadarResponse(BaseModel):
    items: List[RadarItem] = Field(default_factory=list)
    bazin_target_yield: float = 0.06
    below_count: int = 0
    warnings: List[str] = Field(default_factory=list)


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


@router.get("/watchlist/radar", response_model=RadarResponse)
async def watchlist_radar() -> RadarResponse:
    """Radar de zona de compra: preço, DY e situação vs preço-teto de Bazin de TODOS os
    ativos observados — a watchlist deixa de ser lista inerte e responde 'é hora de
    comprar?' sem abrir ativo por ativo. Ordenado pela margem sobre o teto."""
    db = get_db()
    settings = get_settings()
    await watchlist_repo.seed_if_empty(db)
    rows = await watchlist_repo.list_all(db)
    warnings: list[str] = []

    prefs = await preferences_repo.get(db, settings)
    bazin_mode = prefs.get("bazin_target_mode") or "fixed_6"
    cdi = None
    if bazin_mode == "dynamic_selic":
        try:
            cdi = await get_sgs().cdi_annual()
        except Exception:  # noqa: BLE001
            cdi = None
    bazin_yield = resolve_bazin_target_yield(
        bazin_mode, float(prefs.get("bazin_target_yield") or 0.06), cdi
    )

    in_pf: set[str] = set()
    try:
        from app.deps import get_ghostfolio
        from app.services.portfolio_service import get_enriched_portfolio

        pf = await get_enriched_portfolio(get_ghostfolio(), get_cache())
        in_pf = {p.ticker for p in pf.positions}
    except Exception:  # noqa: BLE001
        warnings.append("Carteira indisponível — sem marcação 'já tenho'.")

    tickers = [r["ticker"] for r in rows]
    hints = {r["ticker"]: r.get("asset_class") or "STOCK" for r in rows}
    try:
        assets = await market_data.build_assets(tickers, get_cache(), get_brapi(), hints)
    except Exception as exc:  # noqa: BLE001
        return RadarResponse(warnings=[f"Falha ao buscar dados de mercado: {exc}"])

    items: list[RadarItem] = []
    for a in assets:
        ceiling = _bazin_ceiling_price(a, bazin_yield)
        margin = _bazin_margin(a, bazin_yield)
        items.append(
            RadarItem(
                ticker=a.ticker,
                asset_class=a.asset_class,
                price=a.price,
                dividend_yield=a.fundamentals.dividend_yield,
                dividend_yield_net=a.fundamentals.dividend_yield_net,
                ceiling_price=round(ceiling, 2) if ceiling is not None else None,
                margin=round(margin, 4) if margin is not None else None,
                below_ceiling=None if margin is None else margin > 0,
                in_portfolio=a.ticker in in_pf,
            )
        )
    # maior margem primeiro (zona de compra no topo); sem margem vai para o fim
    items.sort(key=lambda i: (i.margin is None, -(i.margin or 0)))
    return RadarResponse(
        items=items,
        bazin_target_yield=bazin_yield,
        below_count=sum(1 for i in items if i.below_ceiling),
        warnings=warnings,
    )
