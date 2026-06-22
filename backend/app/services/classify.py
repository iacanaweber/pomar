"""Classificação de ativos da B3 em STOCK / FII / ETF / BDR.

Ordem de confiança: StatusInvest (categoria real) → watchlist → dica do Ghostfolio
→ heurística mínima. Não usamos mais "termina em 11 → FII", pois é furada
(AUVP11 é ETF, TAEE11 é ação, ambos terminam em 11).
"""
from __future__ import annotations

from typing import Optional

from app.cache.store import Cache
from app.data.watchlist import CLASS_BY_TICKER, SECTOR_BY_TICKER
from app.providers import statusinvest
from app.util import normalize_ticker

# Setor default por classe quando não há mapa curado nem setor do provedor — garante que
# todo ativo tenha um setor não-nulo (a visão "por setor" fecha 100%, sem "Sem setor" espúrio).
_DEFAULT_SECTOR_BY_CLASS = {
    "ETF": "Diversificado",
    "BDR": "Exterior",
    "FII": "Imobiliário",
    "STOCK": "Outros",
    "UNKNOWN": "Outros",
}


def resolve_sector(ticker: str, asset_class: str, provider_sector: Optional[str]) -> str:
    """Resolve o setor: mapa curado (por ticker) -> setor do provedor -> default por classe.

    O mapa curado vem primeiro de propósito: torna a afinidade BESST determinística e imune
    à grafia do Fundamentus/Ghostfolio. Nunca retorna None.
    """
    curated = SECTOR_BY_TICKER.get(normalize_ticker(ticker))
    if curated:
        return curated
    if provider_sector and provider_sector.strip():
        return provider_sector.strip()
    return _DEFAULT_SECTOR_BY_CLASS.get(asset_class, "Outros")


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
