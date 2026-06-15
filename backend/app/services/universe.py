"""Construção do universo de candidatos.

Candidatos = posições atuais (Ghostfolio) ∪ watchlist curada. Para cada candidato,
busca dados de mercado na brapi e completa classe/setor com o que o Ghostfolio souber
(o Ghostfolio costuma classificar melhor os ativos que você já tem).
"""
from __future__ import annotations

from typing import List

from app.clients.brapi import BrapiClient
from app.data.watchlist import default_universe
from app.models.market import Asset
from app.models.portfolio import Portfolio


async def build_universe(portfolio: Portfolio, brapi: BrapiClient) -> List[Asset]:
    held = {p.ticker.upper() for p in portfolio.positions}
    tickers = list(dict.fromkeys(list(held) + default_universe()))

    assets = await brapi.get_assets(tickers)

    # completa classe/setor a partir do Ghostfolio quando a brapi não trouxe
    pos_by_ticker = {p.ticker.upper(): p for p in portfolio.positions}
    for a in assets:
        pos = pos_by_ticker.get(a.ticker.upper())
        if pos:
            if not a.sector:
                a.sector = pos.sector
            if pos.asset_class and pos.asset_class != "UNKNOWN":
                a.asset_class = pos.asset_class
    return assets
