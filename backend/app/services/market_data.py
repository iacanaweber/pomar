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
from app.services.classify import classify_ticker, resolve_sector
from app.util import normalize_ticker

_sem = asyncio.Semaphore(6)  # educado com os sites (não martelar)


async def build_assets(
    tickers: List[str],
    cache: Cache,
    brapi: Optional[BrapiClient] = None,
    class_hints: Optional[Dict[str, str]] = None,
    bucket_overrides: Optional[Dict[str, str]] = None,
) -> List[Asset]:
    tickers = [t for t in dict.fromkeys(normalize_ticker(t) for t in tickers) if t]
    hints = class_hints or {}

    async def one(t: str) -> Asset:
        # mesma cascata da carteira: override do usuário -> StatusInvest -> watchlist ->
        # dica GF (filtrada) -> heurística
        cls = await classify_ticker(t, cache, hints.get(t), bucket_overrides)
        async with _sem:
            fund = await fundamentus.fetch(t, cache)
            si = await statusinvest.fetch(t, cache, cls)

        fund = fund or {}
        si = si if isinstance(si, dict) else {}
        by_year = si.get("by_year", {})
        trailing_gross = si.get("trailing_365_gross")
        trailing_net = si.get("trailing_365_net")
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

        # DY trailing-365d real (proventos por data, StatusInvest) — bruto e líquido (JCP×0,85);
        # cai para o DY do Fundamentus quando não há histórico recente (sem sobrescrever cegamente).
        dy_net = None
        if price and trailing_gross and trailing_gross > 0:
            dy = round(trailing_gross / price, 4)
            if trailing_net is not None:
                dy_net = round(trailing_net / price, 4)

        # setor canônico (curado -> provedor -> default por classe); nunca None
        sector = resolve_sector(t, cls, sector)

        missing = []
        if pvp is None:
            missing.append("pvp")
        if pl is None:
            missing.append("pl")
        if dy is None:
            missing.append("dividend_yield")
        if not by_year:
            missing.append("dividends_history")
        if price is None:
            missing.append("all")

        src = []
        if fund:
            src.append("fundamentus")
        if si:
            src.append("statusinvest")
        return Asset(
            ticker=t,
            asset_class=cls,
            sector=sector,
            price=price,
            fundamentals=Fundamentals(
                pvp=pvp, pl=pl, dividend_yield=dy, dividend_yield_net=dy_net, lpa=lpa, vpa=vpa,
                roe=fund.get("roe"), net_margin=fund.get("net_margin"),
                net_debt_to_ebitda=fund.get("net_debt_to_ebitda"),
                current_ratio=fund.get("current_ratio"),
                avg_daily_liquidity=fund.get("avg_daily_liquidity"),
            ),
            dividends_by_year=by_year,
            # Lote padrão da B3: ações negociam em lotes de 100 no mercado principal
            # (o fracionário aceita 1); FII/ETF/BDR negociam por 1 cota. O plano usa o
            # lote conforme a preferência lot_mode ('integral' respeita o lote de 100).
            lot_size=100 if cls == "STOCK" else 1,
            missing=missing,
            as_of=datetime.now(timezone.utc).isoformat(),
            source="+".join(src) or "indisponível",
        )

    return await asyncio.gather(*[one(t) for t in tickers])
