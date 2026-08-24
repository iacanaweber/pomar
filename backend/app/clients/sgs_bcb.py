"""Cliente do SGS (Sistema Gerenciador de Séries Temporais) do Banco Central.

Fornece a taxa livre de risco (CDI/Selic) usada como benchmark da renda fixa, o IPCA que
corrige o piso da reserva e, opcionalmente, o atrelamento do DY-alvo de Bazin à Selic.
Cacheado (as séries mudam devagar) com fallback `stale`.

Séries (verificadas ao vivo): 12 = CDI %/dia útil; 1178 = Selic anualizada base 252 (% a.a.);
433 = IPCA, variação % do MÊS. O CDI anual é o diário capitalizado em 252 dias úteis:
(1 + d/100)**252 − 1; o IPCA acumulado é o produto de (1 + v/100) dos meses da janela.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

import httpx

from app.cache.store import Cache

_TTL = 12 * 3600  # 12h — a taxa básica muda em reuniões do COPOM (a cada ~45 dias)
_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados/ultimos/1?formato=json"
_RANGE = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    "?formato=json&dataInicial={start}&dataFinal={end}"
)

IPCA_SERIES = 433


def _br_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _parse_br_date(value: str) -> Optional[date]:
    try:
        return datetime.strptime(str(value).strip(), "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


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

    async def series_range(
        self, code: int, start: date, end: Optional[date] = None
    ) -> Optional[List[dict]]:
        """Observações de uma série no intervalo: [{'date': date, 'value': float}].

        O cliente só sabia pedir o ÚLTIMO valor; o piso corrigido e os benchmarks precisam
        da janela inteira. `None` quando a série não veio e não há cópia em cache — quem
        chama decide o que fazer, porque falha de índice nunca pode derrubar uma tela.
        """
        end = end or date.today()
        if end < start:
            return []
        # Chave por MÊS: as séries daqui são mensais ou de fator diário acumulado, e uma
        # chave com a data de hoje multiplicaria as chamadas sem mudar a resposta.
        key = f"sgs:range:{code}:{start.isoformat()}:{end.strftime('%Y-%m')}"
        cached = self.cache.get(key)
        if cached is not None:
            return [{"date": date.fromisoformat(o["date"]), "value": o["value"]} for o in cached]
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    _RANGE.format(code=code, start=_br_date(start), end=_br_date(end))
                )
            resp.raise_for_status()
            raw = resp.json()
        except Exception:
            stale = self.cache.get_stale(key)
            if stale is None:
                return None
            return [{"date": date.fromisoformat(o["date"]), "value": o["value"]} for o in stale]

        out: List[dict] = []
        for item in raw or []:
            d = _parse_br_date(item.get("data"))
            try:
                v = float(item.get("valor"))
            except (TypeError, ValueError):
                continue
            if d is not None:
                out.append({"date": d, "value": v})
        self.cache.set(key, [{"date": o["date"].isoformat(), "value": o["value"]} for o in out], _TTL)
        return out

    async def ipca_factor_since(self, start: date) -> Optional[float]:
        """Fator acumulado do IPCA desde `start` (1.0 = sem correção). `None` se indisponível.

        Convenção: conta só os meses FECHADOS DEPOIS do mês da data-base. O IPCA de um mês
        mede o mês inteiro; incluir o mês da data-base corrigiria por um período que ainda
        não tinha começado. Errar para menos é o lado certo de errar num piso de reserva.
        """
        obs = await self.series_range(IPCA_SERIES, start)
        if obs is None:
            return None
        factor = 1.0
        for o in obs:
            d = o["date"]
            if (d.year, d.month) <= (start.year, start.month):
                continue
            factor *= 1.0 + o["value"] / 100.0
        return round(factor, 8)
