"""Cliente do SGS (Sistema Gerenciador de Séries Temporais) do Banco Central.

Fornece a taxa livre de risco (CDI/Selic) usada como benchmark da renda fixa e, opcionalmente,
para atrelar o DY-alvo de Bazin à Selic. Cacheado (a taxa muda devagar) com fallback `stale`.

Séries (verificadas ao vivo): 12 = CDI %/dia útil; 1178 = Selic anualizada base 252 (% a.a.).
O CDI anual é o diário capitalizado em 252 dias úteis: (1 + d/100)**252 − 1.
"""
from __future__ import annotations

from typing import Optional

import httpx

from app.cache.store import Cache

_TTL = 12 * 3600  # 12h — a taxa básica muda em reuniões do COPOM (a cada ~45 dias)
_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados/ultimos/1?formato=json"


class SgsClient:
    def __init__(self, cache: Cache) -> None:
        self.cache = cache

    async def _last_value(self, code: int) -> Optional[float]:
        key = f"sgs:{code}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(_BASE.format(code=code))
            resp.raise_for_status()
            data = resp.json()
            value = float(data[-1]["valor"])  # 'valor' é string com ponto decimal
        except Exception:
            return self.cache.get_stale(key)
        self.cache.set(key, value, _TTL)
        return value

    async def cdi_annual(self) -> Optional[float]:
        """CDI anualizado (fração, ex.: 0.1415). Deriva do CDI diário (SGS 12) em base 252."""
        daily_pct = await self._last_value(12)
        if daily_pct is None:
            return None
        return round((1.0 + daily_pct / 100.0) ** 252 - 1.0, 6)

    async def selic_annual(self) -> Optional[float]:
        """Selic anualizada base 252 (fração, ex.: 0.1415) — SGS 1178."""
        v = await self._last_value(1178)
        return round(v / 100.0, 6) if v is not None else None
