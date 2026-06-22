"""Agregador de dados de mercado — combina múltiplos provedores.

- Fundamentus  -> P/L, P/VP, setor, cotação, LPA, VPA (ações e FIIs)
- StatusInvest -> histórico de dividendos por ano (base de Bazin/consistência)
- brapi        -> fallback de cotação (útil p/ ETFs/BDRs ausentes no Fundamentus)

O dividend yield é calculado do histórico real (último ano completo ÷ preço), com o
DY do Fundamentus como reserva. Tudo cacheado nos provedores; aqui só orquestra.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.cache.store import Cache
from app.clients.brapi import BrapiClient
from app.models.market import Asset, Fundamentals
from app.providers import fundamentus, statusinvest
from app.services.classify import classify_ticker
from app.util import normalize_ticker

_sem = asyncio.Semaphore(6)  # educado com os sites (não martelar)


async def build_assets(
    tickers: List[str],
    cache: Cache,
    brapi: Optional[BrapiClient] = None,
    class_hints: Optional[Dict[str, str]] = None,
) -> List[Asset]:
    tickers = [t for t in dict.fromkeys(normalize_ticker(t) for t in tickers) if t]
    hints = class_hints or {}

    async def one(t: str) -> Asset:
        cls = hints.get(t) or await classify_ticker(t, cache)
        async with _sem:
            fund = await fundamentus.fetch(t, cache)
            divs = await statusinvest.fetch(t, cache, cls)

        fund = fund or {}
        price = fund.get("price")
        sector = fund.get("sector")
        pvp, pl, dy = fund.get("pvp"), fund.get("pl"), fund.get("dy")
        lpa, vpa = fund.get("lpa"), fund.get("vpa")  # base do Número de Graham (antes descartados)

        # fallback de cotação/setor via brapi (ETFs/BDRs que não estão no Fundamentus)
        if price is None and brapi is not None:
            try:
                ba = await brapi.get_assets([t])
                if ba and ba[0].price:
                    price = ba[0].price
                    sector = sector or ba[0].sector
            except Exception:
                pass

        # dividend yield do histórico real: último ano completo ÷ preço
        if divs and price:
            last_year = max(divs)
            last_val = divs[last_year]
            if last_val > 0:
                dy = round(last_val / price, 4)

        missing = []
        if pvp is None:
            missing.append("pvp")
        if pl is None:
            missing.append("pl")
        if dy is None:
            missing.append("dividend_yield")
        if not divs:
            missing.append("dividends_history")
        if price is None:
            missing.append("all")

        src = []
        if fund:
            src.append("fundamentus")
        if divs:
            src.append("statusinvest")
        return Asset(
            ticker=t,
            asset_class=cls,
            sector=sector,
            price=price,
            fundamentals=Fundamentals(pvp=pvp, pl=pl, dividend_yield=dy, lpa=lpa, vpa=vpa),
            dividends_by_year=divs,
            lot_size=1,
            missing=missing,
            as_of=datetime.now(timezone.utc).isoformat(),
            source="+".join(src) or "indisponível",
        )

    return await asyncio.gather(*[one(t) for t in tickers])
