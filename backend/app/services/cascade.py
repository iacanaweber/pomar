"""Ordem de prioridade do aporte — a cascata que decide para onde o dinheiro vai.

Três degraus, nesta ordem:

1. **Déficit do piso da reserva.** Primeiro degrau: o piso é o que separa "investir" de
   "ter que vender no pior momento". Só conta de resgate imediato satisfaz esse degrau,
   então o déficit é medido contra a reserva LÍQUIDA. `floor_share` põe um teto em quanto
   do aporte pode ir para cá — sem ele, um déficit grande come aportes inteiros por meses.
2. **Déficit percentual da classe `RENDA_FIXA`**, medido contra TODO o valor da classe
   (inclusive o que está travado — para o peso da carteira, uma LCI vale o que vale). O
   que foi ao piso no degrau 1 já conta aqui: são o mesmo dinheiro.
3. **O que sobrar** vai para a alocação normal entre as demais classes.

Os dois primeiros degraus usam denominadores DIFERENTES de propósito: o piso pergunta
"quanto eu consigo sacar hoje" e o peso pergunta "quanto da carteira está em renda fixa".
Uma LCI travada responde a segunda e não à primeira.

Invariante, verificável com tolerância explícita:
`floor_directed + rf_directed + aporte_rv == aporte`.

Tudo aqui é função pura; as somas acumulam em centavos inteiros.
"""
from __future__ import annotations

from typing import Any, Dict

from app.util import from_cents, to_cents


def split_aporte(
    aporte: float,
    floor_deficit: float,
    rf_class_target: float,
    rf_value: float,
    floor_share: float = 1.0,
) -> Dict[str, Any]:
    """Divide o aporte entre piso, peso da renda fixa e renda variável.

    `rf_class_target` é o alvo em R$ da classe pelo PESO (não o piso — ele entra pelo
    primeiro degrau). `rf_value` é o valor atual da classe inteira.

    `floor_share` (0..1) é o TETO do primeiro degrau: no máximo essa fração do aporte pode
    ir para o piso. É teto, não cota — com o piso já composto o déficit é zero e não há
    sobre o que incidir, então o controle desaparece do cálculo sozinho, sem `if` especial.
    O default 1.0 é a prioridade absoluta de sempre.
    """
    disponivel = to_cents(max(0.0, aporte))

    share = min(1.0, max(0.0, floor_share))
    teto = int(round(disponivel * share))
    sem_teto = min(disponivel, to_cents(max(0.0, floor_deficit)))
    ao_piso = min(teto, sem_teto)
    disponivel -= ao_piso

    # o que foi ao piso já engordou a classe: o déficit percentual é medido depois dele
    apos_piso = to_cents(max(0.0, rf_value)) + ao_piso
    deficit_pct = max(0, to_cents(max(0.0, rf_class_target)) - apos_piso)
    ao_peso = min(disponivel, deficit_pct)
    disponivel -= ao_peso

    return {
        "floor_directed": from_cents(ao_piso),
        "rf_directed": from_cents(ao_peso),
        "rf_total": from_cents(ao_piso + ao_peso),
        "aporte_rv": from_cents(disponivel),
        # o teto cortou algo que iria para o piso? é o que a nota do plano usa para
        # explicar por que só parte do aporte cobriu um déficit maior
        "floor_capped": ao_piso < sem_teto,
    }


def rf_gap(
    rf_class_target: float, rf_value: float, total_after: float
) -> Dict[str, Any]:
    """Gap da classe `RENDA_FIXA` em R$ e em pontos percentuais.

    Renda fixa ACIMA do alvo devolve gap zero — não é erro nem aviso, é uma carteira que
    não precisa de aporte ali. `pp` é 0 quando não há patrimônio: sem denominador, não há
    ponto percentual a reportar (e nunca um `Infinity`).
    """
    falta = max(0, to_cents(max(0.0, rf_class_target)) - to_cents(max(0.0, rf_value)))
    base = to_cents(max(0.0, total_after))
    return {
        "brl": from_cents(falta),
        "pp": round(falta / base * 100, 2) if base > 0 else 0.0,
    }
