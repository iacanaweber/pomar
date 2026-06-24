"""Provedor StatusInvest — histórico de proventos (dividendos + JCP) da B3.

Usa o endpoint JSON interno `companytickerprovents`. Para ações tenta /acao e para
FIIs /fii. Retorna os dividendos somados por ano, preenchendo com 0 os anos sem
pagamento dentro da janela (para a consistência ser medida corretamente).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

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


def _parse_date(value) -> Optional[date]:
    """dd/mm/yyyy -> date (ou None se inválido)."""
    try:
        return datetime.strptime(str(value)[:10], "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


def _net_factor(et: Optional[str]) -> float:
    """Fator líquido por tipo de provento: JCP/tributado sofrem 15% de IR; dividendo/FII isento."""
    s = (et or "").lower()
    if "jcp" in s or "juros sobre capital" in s or "tribut" in s:
        return 0.85
    return 1.0  # 'Dividendo' (isento) e 'Rendimento' de FII (isento p/ PF)


def _trailing_365(payments: List[dict], today: date, net: bool) -> float:
    """Soma dos proventos PAGOS nos últimos 365 dias (por data de pagamento `pd`/`ed`).

    net=True aplica o IR do JCP (×0,85). Pagamentos futuros (pd > hoje) são ignorados.
    """
    cutoff = today - timedelta(days=365)
    total = 0.0
    for it in payments:
        d = _parse_date(it.get("pd") or it.get("ed"))
        v = it.get("v")
        if d is None or v is None or not (cutoff < d <= today):
            continue
        factor = _net_factor(it.get("et")) if net else 1.0
        total += float(v) * factor
    return round(total, 6)


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


async def _fetch_payments(ticker: str, cache: Cache, asset_class: str = "STOCK") -> List[dict]:
    """Lista crua de pagamentos do StatusInvest (compartilhada por fetch e monthly_seasonality)."""
    key = f"statusinvest:pay:{ticker}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    paths = ["fii", "acao"] if asset_class == "FII" else ["acao", "fii"]
    payments: List[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_UA) as client:
            for p in paths:
                resp = await client.get(
                    f"https://statusinvest.com.br/{p}/companytickerprovents",
                    params={"ticker": ticker, "chartProventsType": "2"},
                )
                if resp.status_code == 200:
                    payments = resp.json().get("assetEarningsModels") or []
                    if payments:
                        break
    except Exception:
        return cache.get_stale(key) or []
    cache.set(key, payments, _TTL)
    return payments


async def fetch(ticker: str, cache: Cache, asset_class: str = "STOCK") -> Dict:
    """Proventos do ticker: agregado por ano (Bazin/consistência) + DY trailing-365d bruto e
    líquido (JCP×0,85). Estrutura: {by_year, trailing_365_gross, trailing_365_net}.
    """
    payments = await _fetch_payments(ticker, cache, asset_class)
    if not payments:
        return {}
    today = datetime.now(timezone.utc).date()
    return {
        "by_year": _windowed(payments),
        "trailing_365_gross": _trailing_365(payments, today, net=False),
        "trailing_365_net": _trailing_365(payments, today, net=True),
    }


async def monthly_seasonality(ticker: str, cache: Cache, asset_class: str = "STOCK") -> Dict[int, float]:
    """Provento MÉDIO por mês (1..12) por cota, dos últimos anos completos — mapa sazonal."""
    payments = await _fetch_payments(ticker, cache, asset_class)
    if not payments:
        return {}
    current_year = datetime.now(timezone.utc).year
    by_month: Dict[int, float] = {m: 0.0 for m in range(1, 13)}
    years: set[int] = set()
    for it in payments:
        d = _parse_date(it.get("pd") or it.get("ed"))
        v = it.get("v")
        if d is None or v is None or not (current_year - _WINDOW <= d.year < current_year):
            continue
        by_month[d.month] += float(v)
        years.add(d.year)
    n = len(years) or 1
    return {m: round(by_month[m] / n, 6) for m in range(1, 13)}
