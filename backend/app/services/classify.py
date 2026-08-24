"""Classificação de ativos da B3 em STOCK / FII / ETF / BDR / RENDA_FIXA.

Ordem de confiança: **override do usuário** (rótulo da dimensão `bucket`) → StatusInvest
(categoria real) → watchlist → dica do Ghostfolio → heurística mínima. Não usamos mais
"termina em 11 → FII", pois é furada (AUVP11 é ETF, TAEE11 é ação, ambos terminam em 11).

O passo zero tem precedência ABSOLUTA porque a pergunta que ele responde é outra: o
StatusInvest diz o que o ativo É, e o bucket diz em que cesta o usuário decidiu comprá-lo.
Um ETF de renda fixa (IMAB11, IRFM11, FIXA11) é corretamente um ETF e ainda assim pertence
à cesta `RENDA_FIXA` na carteira alvo de quem o compra por causa do indexador. Quando os
dois discordam, quem manda é a decisão de alocação — é ela que dirige a compra.

Este módulo continua sem I/O de banco: o mapa de overrides chega pronto de quem chama
(`repositories/labels_repo.bucket_overrides`).
"""
from __future__ import annotations

from typing import Dict, Optional

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
    "RENDA_FIXA": "Renda fixa",
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


async def classify_ticker(
    ticker: str,
    cache: Cache,
    gf_hint: Optional[str] = None,
    bucket_overrides: Optional[Dict[str, str]] = None,
) -> str:
    t = normalize_ticker(ticker)
    # 0) override do usuário: a cesta escolhida à mão vence qualquer provedor
    manual = (bucket_overrides or {}).get(t)
    if manual:
        return manual
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
