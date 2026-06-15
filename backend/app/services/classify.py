"""Classificação de ativos da B3 em STOCK / FII / ETF / BDR.

Ordem de confiança: StatusInvest (categoria real) → watchlist → dica do Ghostfolio
→ heurística mínima. Não usamos mais "termina em 11 → FII", pois é furada
(AUVP11 é ETF, TAEE11 é ação, ambos terminam em 11).
"""
from __future__ import annotations

from typing import Optional

from app.cache.store import Cache
from app.data.watchlist import CLASS_BY_TICKER
from app.providers import statusinvest
from app.util import normalize_ticker


async def classify_ticker(ticker: str, cache: Cache, gf_hint: Optional[str] = None) -> str:
    t = normalize_ticker(ticker)
    # 1) fonte confiável
    si = await statusinvest.classify(t, cache)
    if si:
        return si
    # 2) watchlist curada
    if t in CLASS_BY_TICKER:
        return CLASS_BY_TICKER[t]
    # 3) dica do Ghostfolio só quando é positiva (ETF/FII/BDR; EQUITY é pouco confiável p/ FII)
    if gf_hint in ("ETF", "FII", "BDR"):
        return gf_hint
    # 4) heurística mínima (só BDR pelo sufixo; o resto assume ação)
    if t.endswith(("34", "35", "32", "33", "39")):
        return "BDR"
    return "STOCK"
