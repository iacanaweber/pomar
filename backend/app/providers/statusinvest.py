"""Provedor StatusInvest — histórico de proventos (dividendos + JCP) da B3.

Usa o endpoint JSON interno `companytickerprovents`. Para ações tenta /acao e para
FIIs /fii. Retorna os dividendos somados por ano, preenchendo com 0 os anos sem
pagamento dentro da janela (para a consistência ser medida corretamente).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

import httpx

from app.cache.store import Cache

_TTL = 86400  # 24h
_CLASS_TTL = 7 * 86400  # 7 dias (tipo do ativo muda raramente)
_WINDOW = 5  # anos completos considerados (média de Bazin / consistência)
_UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
}


def _windowed(payments: list) -> Dict[str, float]:
    """Soma por ano e preenche a janela de anos completos (zeros incluídos)."""
    current_year = datetime.now(timezone.utc).year
    by_year: Dict[int, float] = {}
    for it in payments:
        date = it.get("pd") or it.get("ed") or ""  # dd/mm/yyyy
        value = it.get("v")
        if len(str(date)) >= 4 and value is not None:
            try:
                year = int(str(date)[-4:])
                by_year[year] = by_year.get(year, 0.0) + float(value)
            except (TypeError, ValueError):
                continue
    if not by_year:
        return {}
    first = min(by_year)
    start = max(first, current_year - _WINDOW)  # janela de anos completos
    out: Dict[str, float] = {}
    for y in range(start, current_year):  # exclui o ano corrente (incompleto)
        out[str(y)] = round(by_year.get(y, 0.0), 4)
    return out


def _url_to_class(url: str) -> str:
    u = (url or "").lower()
    if "/fundos-imobiliarios/" in u or "/fundos-de-investimento/" in u:
        return "FII"
    if "/etfs/" in u:
        return "ETF"
    if "/bdrs/" in u or "/bdr/" in u:
        return "BDR"
    if "/acoes/" in u:
        return "STOCK"
    return ""


async def classify(ticker: str, cache: Cache) -> str | None:
    """Descobre a classe do ativo (STOCK/FII/ETF/BDR) pela categoria do StatusInvest.

    Fonte confiável — evita adivinhar pelo sufixo (ex: AUVP11 é ETF, TAEE11 é ação,
    KNCR11 é FII, todos terminando em 11). Retorna None se não encontrar.
    """
    key = f"statusinvest:class:{ticker}"
    cached = cache.get(key)
    if cached is not None:
        return cached or None
    cls = ""
    try:
        async with httpx.AsyncClient(timeout=12.0, headers=_UA) as client:
            resp = await client.get(
                "https://statusinvest.com.br/home/mainsearchquery", params={"q": ticker}
            )
            items = resp.json()
        if isinstance(items, list):
            for it in items:
                if str(it.get("code", "")).upper() == ticker.upper():
                    cls = _url_to_class(it.get("url", ""))
                    break
    except Exception:
        return None
    cache.set(key, cls, _CLASS_TTL)
    return cls or None


async def fetch(ticker: str, cache: Cache, asset_class: str = "STOCK") -> Dict[str, float]:
    key = f"statusinvest:div:{ticker}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    paths = ["fii", "acao"] if asset_class == "FII" else ["acao", "fii"]
    payments = []
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_UA) as client:
            for p in paths:
                resp = await client.get(
                    f"https://statusinvest.com.br/{p}/companytickerprovents",
                    params={"ticker": ticker, "chartProventsType": "2"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    payments = data.get("assetEarningsModels") or []
                    if payments:
                        break
    except Exception:
        return cache.get_stale(key) or {}
    by_year = _windowed(payments)
    cache.set(key, by_year, _TTL)
    return by_year
