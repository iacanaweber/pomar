"""Provedor Fundamentus — indicadores fundamentalistas da B3 (ações e FIIs).

Lê a página pública detalhes.php e extrai P/L, P/VP, Dividend Yield, setor, cotação,
LPA e VPA. HTML em latin-1. Resultado cacheado por 24h.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

from app.cache.store import Cache

log = logging.getLogger("pomar.fundamentus")
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


def _pct(label_value: Optional[str]) -> Optional[float]:
    """Indicador em % do Fundamentus (ex.: ROE '12,3%') -> fração 0,123."""
    n = _num(label_value)
    return (n / 100) if n is not None else None


def _parse(html: str) -> dict:
    setor = _grab(html, "Setor")
    setor = re.sub(r"<[^>]+>", "", setor).strip() if setor else None
    dy = _grab(html, "Div. Yield")
    # Dív.Líq/EBITDA não existe pronto no Fundamentus; aproximamos por Dív.Líquida ÷ EBIT
    # (EBIT < EBITDA ⇒ razão um pouco mais conservadora). Ambos são valores absolutos na página.
    div_liq = _num(_grab(html, "Dív. Líquida"))
    ebit = _num(_grab(html, "EBIT"))
    net_debt_to_ebit = (div_liq / ebit) if (div_liq is not None and ebit and ebit > 0) else None
    return {
        "pl": _num(_grab(html, "P/L")),
        "pvp": _num(_grab(html, "P/VP")),
        "dy": (_num(dy) / 100) if _num(dy) is not None else None,
        "price": _num(_grab(html, "Cotação")),
        "lpa": _num(_grab(html, "LPA")),
        "vpa": _num(_grab(html, "VPA")),
        "roe": _pct(_grab(html, "ROE")),
        "net_margin": _pct(_grab(html, "Marg. Líquida")),
        "net_debt_to_ebitda": net_debt_to_ebit,  # proxy: Dív.Líquida ÷ EBIT
        "current_ratio": _num(_grab(html, "Liquidez Corr")),
        "avg_daily_liquidity": _num(_grab(html, "Vol $ méd (2m)")),
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
    # HTTP ok mas nada parseado: provável mudança de markup — falha ALTO, não silenciosa.
    if resp.status_code == 200 and len(resp.content) > 1000:
        log.warning(
            "fundamentus parser_suspect: %s respondeu 200 mas nenhum campo-chave foi extraído "
            "(markup pode ter mudado).", ticker
        )
    return None
