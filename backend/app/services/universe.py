"""Construção do universo de candidatos.

Candidatos = posições atuais (Ghostfolio) ∪ candidatos permitidos por classe. Por padrão
os candidatos são a watchlist curada inteira; favoritos (⭐) restringem a classe aos
marcados e a carteira alvo (cesta de pesos) tem precedência sobre ambos. Com foco em uma
classe, só ela entra — o filtro acontece ANTES do fetch de mercado, que domina o tempo
de geração do plano. Os dados de mercado vêm do agregador (Fundamentus + StatusInvest +
brapi). A classe de cada ativo usa, em ordem: Ghostfolio (para o que você já tem) →
watchlist/cesta → heurística.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.cache.store import Cache
from app.clients.brapi import BrapiClient
from app.models.market import Asset
from app.models.portfolio import Portfolio
from app.repositories import watchlist_repo
from app.deps import get_db
from app.services import market_data


async def build_universe(
    portfolio: Portfolio,
    cache: Cache,
    brapi: BrapiClient,
    focus: str = "BALANCE",
    favorites: Optional[Dict[str, List[str]]] = None,
    class_baskets: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[Asset]:
    favorites = favorites or {}
    class_baskets = class_baskets or {}
    focused = None if focus in (None, "", "BALANCE") else focus.upper()

    positions = [
        p for p in portfolio.positions if focused is None or p.asset_class == focused
    ]
    held = {p.ticker.upper() for p in positions}

    # Watchlist editável (SQLite), agrupada por classe; semeada na primeira execução.
    # Fallback para a lista curada estática se o banco falhar.
    watch_by_class: Dict[str, List[str]] = {}
    try:
        db = get_db()
        await watchlist_repo.seed_if_empty(db)
        for row in await watchlist_repo.list_all(db):
            if row.get("valid", 1):
                cls = row.get("asset_class") or "STOCK"
                watch_by_class.setdefault(cls, []).append(row["ticker"])
    except Exception:  # noqa: BLE001
        watch_by_class = {}
    if not watch_by_class:
        from app.data.watchlist import CLASS_BY_TICKER

        for t, cls in CLASS_BY_TICKER.items():
            watch_by_class.setdefault(cls, []).append(t)

    # Candidatos por classe: cesta > favoritos > watchlist inteira. Tickers de cesta
    # entram mesmo fora da watchlist (precisam de cotação para o cálculo de compra).
    candidates: List[str] = []
    class_hints: Dict[str, str] = {}
    for cls in set(watch_by_class) | set(class_baskets) | set(favorites):
        if focused is not None and cls != focused:
            continue
        if class_baskets.get(cls):
            chosen = [t.upper() for t in class_baskets[cls]]
        elif favorites.get(cls):
            chosen = [t.upper() for t in favorites[cls]]
        else:
            chosen = [t.upper() for t in watch_by_class.get(cls, [])]
        candidates.extend(chosen)
        class_hints.update({t: cls for t in chosen})

    tickers = list(dict.fromkeys(list(held) + candidates))

    # dicas de classe a partir do Ghostfolio (mais confiável p/ o que você já tem)
    class_hints.update(
        {
            p.ticker.upper(): p.asset_class
            for p in positions
            if p.asset_class and p.asset_class != "UNKNOWN"
        }
    )

    assets = await market_data.build_assets(tickers, cache, brapi, class_hints)

    # completa setor a partir do Ghostfolio quando o provedor não trouxe
    pos_by_ticker = {p.ticker.upper(): p for p in positions}
    for a in assets:
        pos = pos_by_ticker.get(a.ticker.upper())
        if pos and not a.sector:
            a.sector = pos.sector
    return assets
