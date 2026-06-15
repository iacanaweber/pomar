"""Cliente da brapi.dev — cotação, fundamentos e dividendos da B3.

- Requisições EM LOTE (vários tickers por chamada) para economizar quota.
- Cache por ativo (TTL) com fallback para cache defasado quando a API falha.
- Parser defensivo: o tier grátis varia os campos, então cada dado ausente vira None
  (e a métrica correspondente fica `available=False` no score — nunca inventamos número).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from app.cache.store import Cache
from app.models.market import Asset, Fundamentals
from app.util import normalize_ticker

_QUOTE_TTL = 3600  # 1h (cotação + fundamentos para uso diário de aporte)
_MODULES = "summaryProfile,defaultKeyStatistics,financialData"


def _dig(d: dict, *keys) -> Optional[float]:
    """Procura a primeira chave existente (em vários níveis comuns da brapi)."""
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                return None
    for sub in ("defaultKeyStatistics", "summaryDetail", "financialData"):
        node = d.get(sub)
        if isinstance(node, dict):
            for k in keys:
                if node.get(k) is not None:
                    try:
                        return float(node[k])
                    except (TypeError, ValueError):
                        pass
    return None


def _dividends_by_year(node: dict) -> Dict[str, float]:
    out: Dict[str, float] = {}
    div = node.get("dividendsData") or {}
    cash = div.get("cashDividends") or []
    for item in cash:
        date = item.get("paymentDate") or item.get("lastDatePrior") or ""
        rate = item.get("rate")
        if not date or rate is None:
            continue
        year = str(date)[:4]
        try:
            out[year] = out.get(year, 0.0) + float(rate)
        except (TypeError, ValueError):
            continue
    return out


def _sector(node: dict) -> Optional[str]:
    prof = node.get("summaryProfile") or {}
    return prof.get("sector") or prof.get("industry")


class BrapiClient:
    def __init__(self, base_url: str, token: str, cache: Cache, batch_size: int = 1) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.cache = cache
        self.batch_size = max(1, batch_size)
        self._sem = asyncio.Semaphore(3)  # limita concorrência

    async def health(self) -> bool:
        # Usa um ticker que EXIGE token (BBAS3). Assim `brapi: true` significa que o
        # token está válido — PETR4/VALE3/ITUB4/MGLU3 funcionam mesmo sem token e
        # mascarariam um token ausente.
        try:
            assets = await self.get_assets(["BBAS3"])
            return bool(assets and assets[0].price)
        except Exception:
            return False

    async def get_assets(self, tickers: List[str]) -> List[Asset]:
        """Retorna Assets para os tickers, usando cache quando possível."""
        # normaliza (remove .SA do Ghostfolio) e remove duplicatas preservando ordem
        tickers = [t for t in dict.fromkeys(normalize_ticker(t) for t in tickers) if t]
        result: List[Asset] = []
        to_fetch: List[str] = []
        for t in tickers:
            cached = self.cache.get(f"brapi:asset:{t}")
            if cached:
                result.append(Asset(**cached))
            else:
                to_fetch.append(t)

        for i in range(0, len(to_fetch), self.batch_size):
            chunk = to_fetch[i : i + self.batch_size]
            result.extend(await self._fetch_chunk(chunk))
        return result

    async def _fetch_chunk(self, chunk: List[str]) -> List[Asset]:
        params = {
            "range": "1d",
            "fundamental": "true",
            "dividends": "true",
            "modules": _MODULES,
        }
        # A brapi exige o token no header Authorization: Bearer (o ?token= não é
        # honrado nesta versão). Mantemos o header como forma autoritativa.
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        url = f"{self.base_url}/quote/{','.join(chunk)}"
        try:
            async with self._sem:
                data = await self._request_with_backoff(url, params, headers)
            nodes = {n.get("symbol", "").upper(): n for n in data.get("results", [])}
        except Exception:
            nodes = {}

        out: List[Asset] = []
        for t in chunk:
            node = nodes.get(t)
            if node:
                asset = self._parse(t, node)
                self.cache.set(f"brapi:asset:{t}", asset.model_dump(), _QUOTE_TTL)
            else:
                stale = self.cache.get_stale(f"brapi:asset:{t}")
                if stale:
                    asset = Asset(**stale)
                    asset.stale = True
                else:
                    asset = Asset(ticker=t, missing=["all"], source="brapi")
            out.append(asset)
        return out

    async def _request_with_backoff(
        self, url: str, params: dict, headers: dict | None = None, retries: int = 3
    ) -> dict:
        delay = 1.0
        async with httpx.AsyncClient(timeout=20.0) as client:
            for attempt in range(retries):
                resp = await client.get(url, params=params, headers=headers or {})
                if resp.status_code == 429:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                resp.raise_for_status()
                return resp.json()
        resp.raise_for_status()
        return {}

    def _parse(self, ticker: str, node: dict) -> Asset:
        price = _dig(node, "regularMarketPrice", "regularMarketPreviousClose")
        pvp = _dig(node, "priceToBook")
        pl = _dig(node, "priceEarnings", "trailingPE")
        dy = _dig(node, "dividendYield", "trailingAnnualDividendYield")
        if dy is not None and dy > 1.5:  # brapi às vezes devolve em %
            dy = dy / 100.0
        market_cap = _dig(node, "marketCap")
        sector = _sector(node)
        divs = _dividends_by_year(node)

        missing = []
        if pvp is None:
            missing.append("pvp")
        if pl is None:
            missing.append("pl")
        if dy is None:
            missing.append("dividend_yield")
        if not divs:
            missing.append("dividends_history")

        asset_class = _infer_class(node, ticker)
        return Asset(
            ticker=ticker,
            name=node.get("longName") or node.get("shortName"),
            asset_class=asset_class,
            sector=sector,
            price=price,
            fundamentals=Fundamentals(pvp=pvp, pl=pl, dividend_yield=dy, market_cap=market_cap),
            dividends_by_year=divs,
            lot_size=1,
            missing=missing,
            as_of=datetime.now(timezone.utc).isoformat(),
            source="brapi",
        )


def _infer_class(node: dict, ticker: str) -> str:
    t = node.get("type") or ""
    if t == "fund" or ticker.endswith("11"):
        # 11 pode ser FII, ETF ou Unit; heurística simples
        return "FII"
    if ticker.endswith(("34", "35", "32", "33")):
        return "BDR"
    return "STOCK"
