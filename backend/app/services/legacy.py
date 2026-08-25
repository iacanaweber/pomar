"""Posições fora da carteira alvo — o que elas valem e o que cobririam se virassem caixa.

Uma posição está fora do alvo quando o peso-alvo dela é zero: ou o ticker não está em
cesta nenhuma, ou está numa classe cuja meta é 0%. É a situação real de quem mudou de
estratégia e ainda não vendeu.

O número que este módulo produz é **aritmética, não sugestão de venda**: "R$ X em ativos
fora do alvo cobririam Y% do que falta comprar hoje". O app não recomenda vender — o que
ele faz é responder quanto do gap está parado em capital que já não segue a estratégia,
porque essa é uma informação que o usuário não consegue estimar de cabeça.

Função pura sobre listas de dicts; somas em centavos inteiros.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.util import from_cents, normalize_ticker, to_cents


def legacy_positions(
    positions: Iterable[Dict[str, Any]],
    class_baskets: Optional[Dict[str, Dict[str, float]]] = None,
    targets: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """Posições cujo peso-alvo é zero, da maior para a menor.

    Só considera classes que o app sabe comprar: uma posição atribuída ao bucket de renda
    fixa não é "legado", é parte da classe `RENDA_FIXA` — cuja cesta é de indexadores.
    """
    cestas = class_baskets or {}
    alvos = targets or {}
    no_alvo = {
        normalize_ticker(t)
        for c, b in cestas.items()
        if b and alvos.get(c, 0.0) > 0
        for t, w in b.items()
        if w > 0
    }
    out = [
        {"ticker": normalize_ticker(p["ticker"]), "asset_class": p.get("asset_class"),
         "value": float(p.get("value") or 0.0)}
        for p in positions
        if normalize_ticker(p["ticker"]) not in no_alvo
        and (p.get("value") or 0) > 0
        and p.get("asset_class") != "RENDA_FIXA"
    ]
    return sorted(out, key=lambda p: p["value"], reverse=True)


def coverage(legacy_value: float, gap: float) -> Optional[float]:
    """Fração do gap que o legado cobriria (0..1+). `None` quando não há gap a cobrir.

    `None` e não `0.0`: sem gap, a pergunta não se aplica, e devolver zero faria a tela
    dizer "cobriria 0% do gap" — que se lê como "não adiantaria nada".
    """
    gap_cents = to_cents(max(0.0, gap))
    if gap_cents <= 0:
        return None
    return round(to_cents(max(0.0, legacy_value)) / gap_cents, 4)


def summarize(
    positions: Iterable[Dict[str, Any]],
    gap: float,
    class_baskets: Optional[Dict[str, Dict[str, float]]] = None,
    targets: Optional[Dict[str, float]] = None,
) -> Optional[Dict[str, Any]]:
    """Resumo do legado para o plano. `None` quando não há nada fora do alvo."""
    itens = legacy_positions(positions, class_baskets, targets)
    if not itens:
        return None
    total = from_cents(sum(to_cents(p["value"]) for p in itens))
    return {
        "value": total,
        "tickers": [p["ticker"] for p in itens],
        "gap": round(max(0.0, gap), 2),
        "gap_coverage": coverage(total, gap),
    }
