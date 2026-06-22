"""Leitura enriquecida da carteira: classifica corretamente cada posição (FII/ETF/...)
e recalcula a alocação por classe. Usado pela aba 'Minha carteira' e pelo plano.
"""
from __future__ import annotations

from app.cache.store import Cache
from app.clients.ghostfolio import GhostfolioClient
from app.models.portfolio import Allocations, Portfolio
from app.services.classify import classify_ticker, resolve_sector


async def get_enriched_portfolio(ghostfolio: GhostfolioClient, cache: Cache) -> Portfolio:
    pf = await ghostfolio.get_portfolio()

    by_class: dict[str, float] = {}
    by_sector: dict[str, float] = {}
    for p in pf.positions:
        p.asset_class = await classify_ticker(p.ticker, cache, p.asset_class)
        p.sector = resolve_sector(p.ticker, p.asset_class, p.sector)
        by_class[p.asset_class] = by_class.get(p.asset_class, 0.0) + p.weight
        by_sector[p.sector] = by_sector.get(p.sector, 0.0) + p.weight

    pf.allocations = Allocations(by_class=by_class, by_sector=by_sector)
    return pf
