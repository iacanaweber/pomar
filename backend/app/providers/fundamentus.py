"""Provedor Fundamentus — indicadores fundamentalistas da B3 (ações e FIIs).

Lê a página pública detalhes.php e extrai P/L, P/VP, Dividend Yield, setor, cotação,
LPA e VPA. HTML em latin-1. Resultado cacheado por 24h.
"""
from __future__ import annotations

import re
from typing import Optional

import httpx

from app.cache.store import Cache

_TTL = 86400  # 24h
_UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
}


def _num(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    s = re.sub(r"<[^>]+>", " ", raw)
    s = s.replace("%", "").strip()
    s = s.replace(".", "").replace(",", ".")  # 1.234,56 -> 1234.56
    try:
        return float(s)
    except ValueError:
        return None


def _grab(html: str, label: str) -> Optional[str]:
    m = re.search(
        r'<span class="txt">' + re.escape(label) + r"</span></td>\s*"
        r'<td[^>]*class="data[^"]*"[^>]*>\s*<span class="txt">(.*?)</span>',
        html,
        re.S,
    )
    return m.group(1) if m else None


def _parse(html: str) -> dict:
    setor = _grab(html, "Setor")
    setor = re.sub(r"<[^>]+>", "", setor).strip() if setor else None
    dy = _grab(html, "Div. Yield")
    return {
        "pl": _num(_grab(html, "P/L")),
        "pvp": _num(_grab(html, "P/VP")),
        "dy": (_num(dy) / 100) if _num(dy) is not None else None,
        "price": _num(_grab(html, "Cotação")),
        "lpa": _num(_grab(html, "LPA")),
        "vpa": _num(_grab(html, "VPA")),
        "sector": setor,
    }


async def fetch(ticker: str, cache: Cache) -> Optional[dict]:
    key = f"fundamentus:{ticker}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_UA) as client:
            resp = await client.get(
                f"https://www.fundamentus.com.br/detalhes.php?papel={ticker}"
            )
        data = _parse(resp.content.decode("latin-1"))
    except Exception:
        return cache.get_stale(key)
    # só cacheia se veio algo útil (ETFs/BDRs não existem no Fundamentus)
    if any(data.get(k) is not None for k in ("price", "pl", "pvp", "dy")):
        cache.set(key, data, _TTL)
        return data
    return None
