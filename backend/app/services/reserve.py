"""Piso da reserva de emergência — lógica pura.

**Não existe reserva de emergência separada.** A emergência mora em Tesouro Selic, que é ao
mesmo tempo reserva e alocação em renda fixa; manter os dois conceitos faria o mesmo
dinheiro aparecer duas vezes no patrimônio. Por isso o antigo `reserve_target` (uma fração
do patrimônio) foi aposentado como percentual e renasceu como **piso em valor absoluto
dentro da classe `RENDA_FIXA`**:

    alvo_RF_em_R$ = max(peso_RF × patrimônio_total, piso_corrigido)

O comportamento que isso produz é o objetivo: com piso de R$30.000, peso de 20% e
patrimônio de R$100.000, o alvo é R$30.000 — havendo R$30.000, o déficit é zero e nenhum
aporte vai para a renda fixa. Conforme o patrimônio cresce o piso perde relevância sozinho,
e quando `peso × patrimônio` ultrapassa o piso a classe volta a receber aporte pela regra
percentual, sem intervenção. Um saque faz o déficit reaparecer.

Não há carve-out (calcular as porcentagens sobre `patrimônio − piso`): isso faria o app
exibir 20% de renda fixa quando a composição real é 44%, e composição exibida que não
corresponde à realidade é inaceitável aqui.

**Só liquidez imediata satisfaz o piso.** Uma LCI com carência de dois anos soma
normalmente no peso percentual da classe, mas não conta para o piso — sem essa regra o app
mostraria a reserva como cumprida enquanto o dinheiro está travado, que é precisamente a
falha que a reserva existe para evitar. Quem separa o joio é `fixed_income.is_immediately_liquid`;
aqui a `reserva_liquida` já chega somada.

Correção monetária: um piso nominal encolhe sozinho — a 4,5% ao ano, R$30.000 valem cerca
de R$19.000 em dez anos e o número na tela nunca avisa. Com `index='ipca'` o piso efetivo é
`nominal × fator acumulado do IPCA desde a data-base`. Falha do SGS nunca quebra a tela:
sem o fator, vale o nominal e a resposta diz que a correção está indisponível.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.util import from_cents, to_cents


def corrected_floor(
    nominal: float, index: str = "none", ipca_factor: Optional[float] = None
) -> Dict[str, Any]:
    """Piso efetivo em R$. Devolve também se a correção pedida estava disponível."""
    base = max(0.0, float(nominal or 0.0))
    if index != "ipca":
        return {"amount": round(base, 2), "index": index or "none", "available": True}
    if ipca_factor is None or ipca_factor <= 0:
        # Sem o IPCA, o piso nominal é a resposta honesta — e a tela precisa dizer isso.
        return {"amount": round(base, 2), "index": "ipca", "available": False}
    return {
        "amount": from_cents(to_cents(base * float(ipca_factor))),
        "index": "ipca",
        "available": True,
    }


def floor_status(
    floor_nominal: float,
    liquid_reserve: float,
    index: str = "none",
    ipca_factor: Optional[float] = None,
    floor_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Status do piso: nominal, corrigido, reserva líquida, déficit e fração preenchida.

    `pct_filled` é 1.0 quando não há piso configurado — sem alvo não há o que preencher, e
    devolver 0 faria a barra da tela acusar uma falta que não existe.
    """
    floor = corrected_floor(floor_nominal, index, ipca_factor)
    alvo = to_cents(floor["amount"])
    atual = to_cents(max(0.0, liquid_reserve))
    deficit = max(0, alvo - atual)
    return {
        "floor_nominal": round(max(0.0, float(floor_nominal or 0.0)), 2),
        "floor_corrected": floor["amount"],
        "floor_date": floor_date,
        "index": floor["index"],
        "index_available": floor["available"],
        "liquid_reserve": from_cents(atual),
        "deficit": from_cents(deficit),
        "pct_filled": round(min(1.0, atual / alvo), 4) if alvo > 0 else 1.0,
    }


def rf_target_amount(class_weight: float, total_portfolio: float, floor_corrected: float) -> float:
    """Alvo em R$ da classe RENDA_FIXA: o maior entre o peso percentual e o piso."""
    percentual = to_cents(max(0.0, class_weight) * max(0.0, total_portfolio))
    return from_cents(max(percentual, to_cents(max(0.0, floor_corrected))))


def direct_to_floor(aporte: float, floor_deficit: float) -> Dict[str, float]:
    """Primeiro degrau da cascata do aporte: cobrir o déficit do piso.

    Prioridade absoluta e sem sutileza — o piso é o que separa "investir" de "não precisar
    vender no pior momento". Devolve {floor_directed, remaining}.
    """
    disponivel = to_cents(max(0.0, aporte))
    dirigido = min(disponivel, to_cents(max(0.0, floor_deficit)))
    return {
        "floor_directed": from_cents(dirigido),
        "remaining": from_cents(disponivel - dirigido),
    }
