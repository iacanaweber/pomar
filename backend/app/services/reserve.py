"""Reserva / renda fixa na alocação do aporte (lógica pura).

Disciplina Barsi/Bazin: completar a RESERVA (caixa/RF) antes de comprar renda variável, e não
comprar RV cara (acima do preço-teto) — a sobra "por estar tudo caro" também vai à reserva.

`reserve_target` é a fração-alvo do patrimônio TOTAL (RV + reserva) que deve ficar em RF/caixa.
`reserve_current` é quanto já existe em reserva (vem do rastreador de renda fixa).
"""
from __future__ import annotations

from typing import Dict


def split_aporte_reserva(
    aporte: float, total_rv: float, reserve_current: float, reserve_target: float
) -> Dict[str, float]:
    """Divide o aporte entre completar a reserva e a renda variável.

    Retorna {reserve_directed, aporte_rv}. A reserva é priorizada até atingir
    `reserve_target * patrimônio_resultante`. `reserve_target<=0` => tudo vai para RV.
    """
    aporte = max(0.0, aporte)
    if reserve_target <= 0 or aporte <= 0:
        return {"reserve_directed": 0.0, "aporte_rv": round(aporte, 2)}
    total_after = total_rv + reserve_current + aporte
    reserve_need = max(0.0, reserve_target * total_after - reserve_current)
    directed = min(reserve_need, aporte)
    return {"reserve_directed": round(directed, 2), "aporte_rv": round(aporte - directed, 2)}


def reserve_status(
    total_rv: float, reserve_current: float, reserve_target: float, aporte: float = 0.0
) -> Dict[str, float]:
    """Resumo da reserva para exibir (alvo R$, atual, gap, % preenchido)."""
    total_after = total_rv + reserve_current + max(0.0, aporte)
    target_amount = max(0.0, reserve_target) * total_after
    gap = max(0.0, target_amount - reserve_current)
    pct = (reserve_current / target_amount) if target_amount > 0 else 1.0
    return {
        "target_amount": round(target_amount, 2),
        "current_amount": round(reserve_current, 2),
        "gap": round(gap, 2),
        "pct_filled": round(min(1.0, pct), 4),
    }
