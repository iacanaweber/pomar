"""Construção do universo de candidatos.

Duas formas de uso, bem diferentes:

- **com carteira alvo** (o plano): os candidatos são EXATAMENTE os tickers das cestas
  selecionadas. Nada mais precisa de cotação — o que não está na carteira alvo não pode
  ser comprado, e o fetch de mercado é o que domina o tempo de geração do plano.
- **sem carteira alvo** (GET /universe, inspeção): posições atuais ∪ watchlist curada.

A classe de cada ativo usa, em ordem: cesta → Ghostfolio (para o que você já tem) →
watchlist → heurística. Os dados vêm do agregador (Fundamentus + StatusInvest + brapi).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.cache.store import Cache
from app.clients.brapi import BrapiClient
from app.deps import get_db
from app.models.market import Asset
from app.models.portfolio import Portfolio
from app.repositories import watchlist_repo
from app.services import market_data


async def _watchlist_by_class() -> Dict[str, List[str]]:
    """Watchlist editável (SQLite), agrupada por classe; semeada na primeira execução.
    Cai para a lista curada estática se o banco falhar."""
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
    return watch_by_class


async def build_universe(
    portfolio: Portfolio,
    cache: Cache,
    brapi: BrapiClient,
    class_baskets: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[Asset]:
    baskets = {c: b for c, b in (class_baskets or {}).items() if b}
    class_hints: Dict[str, str] = {}

    if baskets:
        tickers: List[str] = []
        for cls, basket in sorted(baskets.items()):
            for t in basket:
                tu = t.upper()
                tickers.append(tu)
                class_hints[tu] = cls
        tickers = list(dict.fromkeys(tickers))
    else:
        watch_by_class = await _watchlist_by_class()
        candidates: List[str] = []
        for cls, ticks in watch_by_class.items():
            chosen = [t.upper() for t in ticks]
            candidates.extend(chosen)
            class_hints.update({t: cls for t in chosen})
        held = [p.ticker.upper() for p in portfolio.positions]
        tickers = list(dict.fromkeys(held + candidates))

    # dicas de classe a partir do Ghostfolio (mais confiável p/ o que você já tem)
    class_hints.update(
        {
            p.ticker.upper(): p.asset_class
            for p in portfolio.positions
            if p.asset_class and p.asset_class != "UNKNOWN" and p.ticker.upper() not in class_hints
        }
    )

    assets = await market_data.build_assets(tickers, cache, brapi, class_hints)

    # completa setor a partir do Ghostfolio quando o provedor não trouxe
    pos_by_ticker = {p.ticker.upper(): p for p in portfolio.positions}
    for a in assets:
        pos = pos_by_ticker.get(a.ticker.upper())
        if pos and not a.sector:
            a.sector = pos.sector
    return assets
