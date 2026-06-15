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
        self.last_diagnostic: dict = {}

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
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        async with self._sem:
            data, diag = await self._fetch_quote(",".join(chunk), headers)
        self.last_diagnostic = diag
        results = data.get("results") if data else None
        nodes = {n.get("symbol", "").upper(): n for n in (results or [])}

        out: List[Asset] = []
        for t in chunk:
            node = nodes.get(t)
            if node and node.get("regularMarketPrice") is not None:
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

    async def _raw_get(self, url: str, params: dict, headers: dict):
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params=params, headers=headers or {})
            try:
                data = resp.json()
            except Exception:
                data = None
            return resp.status_code, data, resp.text

    async def _fetch_quote(self, tickers_csv: str, headers: dict):
        """Busca cotação tentando do mais completo ao mínimo.

        O plano grátis da brapi pode não liberar os `modules` (dados financeiros
        profundos); nesse caso a requisição completa falha e caímos para uma versão
        sem módulos. Retorna (data, diagnóstico) — sem nunca lançar exceção.
        """
        base = {"range": "1d", "fundamental": "true", "dividends": "true"}
        attempts = [
            {**base, "modules": _MODULES},  # completo (ideal)
            base,  # sem módulos (provável no plano grátis)
            {"fundamental": "true", "dividends": "true"},  # mínimo
        ]
        url = f"{self.base_url}/quote/{tickers_csv}"
        diag: dict = {}
        for i, params in enumerate(attempts):
            delay = 1.0
            status, data, text = 0, None, ""
            for _ in range(2):
                try:
                    status, data, text = await self._raw_get(url, params, headers)
                except Exception as exc:  # noqa: BLE001
                    status, data, text = -1, None, repr(exc)
                if status == 429:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                break
            diag = {
                "attempt": i,
                "status": status,
                "params": list(params.keys()),
                "body_snippet": (text or "")[:280],
            }
            if status == 200 and data and data.get("results"):
                return data, diag
        return None, diag

    async def diagnose(self, ticker: str = "BBAS3") -> dict:
        """Diagnóstico de conectividade/token (sem expor o token em si)."""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        data, diag = await self._fetch_quote(normalize_ticker(ticker), headers)
        results = (data or {}).get("results") or []
        return {
            "ticker": normalize_ticker(ticker),
            "token_present": bool(self.token),
            "token_len": len(self.token or ""),
            "base_url": self.base_url,
            "auth_method": "Authorization: Bearer" if self.token else "nenhum",
            "got_price": bool(results and results[0].get("regularMarketPrice") is not None),
            **diag,
        }

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
