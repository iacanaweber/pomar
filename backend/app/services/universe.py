"""Construção do universo de candidatos.

Candidatos = posições atuais (Ghostfolio) ∪ watchlist curada. Os dados de mercado
vêm do agregador (Fundamentus + StatusInvest + brapi). A classe de cada ativo usa,
em ordem: Ghostfolio (para o que você já tem) → watchlist → heurística.
"""
from __future__ import annotations

from typing import List

from app.cache.store import Cache
from app.clients.brapi import BrapiClient
from app.data.watchlist import default_universe
from app.deps import get_db
from app.models.market import Asset
from app.models.portfolio import Portfolio
from app.repositories import watchlist_repo
from app.services import market_data


async def build_universe(portfolio: Portfolio, cache: Cache, brapi: BrapiClient) -> List[Asset]:
    held = {p.ticker.upper() for p in portfolio.positions}

    # Universo de candidatos vem da watchlist editável (SQLite); na primeira execução
    # é semeada com a lista curada. Fallback para a lista estática se o banco falhar.
    try:
        db = get_db()
        await watchlist_repo.seed_if_empty(db)
        watchlist = await watchlist_repo.tickers(db)
    except Exception:  # noqa: BLE001
        watchlist = []
    watchlist = watchlist or default_universe()

    tickers = list(dict.fromkeys(list(held) + watchlist))

    # dicas de classe a partir do Ghostfolio (mais confiável p/ o que você já tem)
    class_hints = {
        p.ticker.upper(): p.asset_class
        for p in portfolio.positions
        if p.asset_class and p.asset_class != "UNKNOWN"
    }

    assets = await market_data.build_assets(tickers, cache, brapi, class_hints)

    # completa setor a partir do Ghostfolio quando o provedor não trouxe
    pos_by_ticker = {p.ticker.upper(): p for p in portfolio.positions}
    for a in assets:
        pos = pos_by_ticker.get(a.ticker.upper())
        if pos and not a.sector:
            a.sector = pos.sector
    return assets
