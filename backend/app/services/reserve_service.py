"""Orquestração do piso da reserva: junta preferências, IPCA e reserva líquida.

`services/reserve.py` é aritmética pura e não fala com ninguém. Este módulo é a camada
fina que busca o fator do IPCA e devolve o status pronto — mesma divisão que existe entre
`services/analytics.py` e `services/portfolio_service.py`.

Existe para que a aba Reserva e o Plantar mostrem o MESMO piso corrigido. Duplicar a
resolução nas duas rotas garantiria que um dia elas divergissem, e um piso que muda de
valor conforme a tela é pior que nenhum piso.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from app.clients.sgs_bcb import SgsClient
from app.services import reserve as reserve_svc


async def resolve_floor(
    prefs: Dict[str, Any],
    liquid_reserve: float,
    sgs: Optional[SgsClient] = None,
    floor_override: Optional[float] = None,
) -> Dict[str, Any]:
    """Status do piso já corrigido. Falha do SGS não levanta: cai no nominal e sinaliza."""
    nominal = (
        floor_override if floor_override is not None
        else float(prefs.get("reserve_floor_amount") or 0.0)
    )
    index = str(prefs.get("reserve_floor_index") or "none")
    base = prefs.get("reserve_floor_date")

    factor = None
    if nominal > 0 and index == "ipca" and base and sgs is not None:
        try:
            factor = await sgs.ipca_factor_since(date.fromisoformat(str(base)[:10]))
        except Exception:  # noqa: BLE001
            factor = None  # o campo `index_available` do status já conta essa história

    return reserve_svc.floor_status(nominal, liquid_reserve, index, factor, base)
