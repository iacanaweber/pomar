"""Leitura enriquecida da carteira: classifica corretamente cada posição (FII/ETF/...)
e recalcula a alocação por classe. Usado pela aba 'Minha carteira' e pelo plano.

A carteira é a fonte de metade das telas e era o ÚNICO dado sem fallback stale: um
restart do Ghostfolio derrubava Carteira, Renda, Meta e Calendário juntos. Agora ela
tem cache curto (menos chamadas repetidas) + cópia stale para degradar com aviso.
"""
from __future__ import annotations

import hashlib
from typing import Dict, Optional

from app.cache.store import Cache
from app.clients.ghostfolio import GhostfolioClient
from app.models.portfolio import Allocations, Portfolio
from app.services.classify import classify_ticker, resolve_sector

_TTL = 120  # 2 min: Carteira/Renda/Meta/Calendário iteram positions em sequência
_KEY = "portfolio:enriched"


def _cache_key(bucket_overrides: Optional[Dict[str, str]]) -> str:
    """A classificação faz parte do que é cacheado, então o override entra na chave.

    Sem isso, mover um ativo de cesta continuaria mostrando a classificação antiga por até
    dois minutos — tempo suficiente para o usuário concluir que o app ignorou a escolha.
    """
    if not bucket_overrides:
        return _KEY
    assinatura = ";".join(f"{t}={c}" for t, c in sorted(bucket_overrides.items()))
    return f"{_KEY}:{hashlib.sha1(assinatura.encode()).hexdigest()[:10]}"


async def get_enriched_portfolio(
    ghostfolio: GhostfolioClient,
    cache: Cache,
    bucket_overrides: Optional[Dict[str, str]] = None,
) -> Portfolio:
    key = _cache_key(bucket_overrides)
    cached = cache.get(key)
    if cached is not None:
        return Portfolio.model_validate(cached)

    try:
        pf = await ghostfolio.get_portfolio()
    except Exception:
        stale = cache.get_stale(key)
        if stale is None:
            raise
        pf = Portfolio.model_validate(stale)
        pf.source = "ghostfolio (cache defasado)"
        pf.warnings = [
            *pf.warnings,
            f"Ghostfolio indisponível — usando a última carteira conhecida (de {pf.as_of}).",
        ]
        return pf

    by_class: dict[str, float] = {}
    by_sector: dict[str, float] = {}
    for p in pf.positions:
        p.asset_class = await classify_ticker(p.ticker, cache, p.asset_class, bucket_overrides)
        p.sector = resolve_sector(p.ticker, p.asset_class, p.sector)
        by_class[p.asset_class] = by_class.get(p.asset_class, 0.0) + p.weight
        by_sector[p.sector] = by_sector.get(p.sector, 0.0) + p.weight

    pf.allocations = Allocations(by_class=by_class, by_sector=by_sector)
    cache.set(key, pf.model_dump(), _TTL)
    return pf
