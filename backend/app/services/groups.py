"""Agrupamento de tickers: um slot da cesta com ticker de compra + tickers legados.

O formato expandido do `class_targets` aceita `float` (peso simples) ou
`{"weight": float, "also": [str]}` (grupo). O ticker-chave recebe aportes; os `also`
são posições mantidas que contam para o mesmo peso-alvo mas não recebem compra.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


def expand_basket(
    basket: Dict[str, Any],
) -> Tuple[Dict[str, float], Dict[str, List[str]]]:
    """Separa a cesta no formato plano (buy_weights) e nos grupos (buy -> legacies).

    buy_weights: {ticker: weight} — formato que o alocador já espera.
    groups: {buy_ticker: [legacy_tickers]} — só entradas com also.
    """
    buy_weights: Dict[str, float] = {}
    groups: Dict[str, List[str]] = {}
    for ticker, entry in basket.items():
        if isinstance(entry, dict):
            buy_weights[ticker] = float(entry.get("weight", 0))
            also = entry.get("also") or []
            if also:
                groups[ticker] = list(also)
        else:
            buy_weights[ticker] = float(entry)
    return buy_weights, groups


def merge_held(
    held: Dict[str, float], groups: Dict[str, List[str]]
) -> Dict[str, float]:
    """Dobra o valor dos legacy tickers no buy ticker e os remove do dict.

    Ex: held={VWRA11: 8000, MUND11: 2000}, groups={MUND11: [VWRA11]}
    → {MUND11: 10000}  (VWRA11 some do dict)
    """
    out = dict(held)
    for buy, legacies in groups.items():
        for leg in legacies:
            if leg in out:
                out[buy] = out.get(buy, 0.0) + out.pop(leg)
    return out


def all_tickers_in_groups(groups: Dict[str, List[str]]) -> Set[str]:
    """Todos os tickers de todos os grupos (buy + legacy)."""
    result: Set[str] = set()
    for buy, legacies in groups.items():
        result.add(buy)
        result.update(legacies)
    return result


def also_tickers(groups: Dict[str, List[str]]) -> Set[str]:
    """Só os tickers legados (os `also`)."""
    result: Set[str] = set()
    for legacies in groups.values():
        result.update(legacies)
    return result


def expand_all_baskets(
    all_baskets: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, List[str]]]]:
    """Expande todas as cestas de uma vez.

    Retorna (flat_baskets, groups_by_class).
    """
    flat: Dict[str, Dict[str, float]] = {}
    groups_by_class: Dict[str, Dict[str, List[str]]] = {}
    for cls, basket in all_baskets.items():
        bw, grps = expand_basket(basket)
        flat[cls] = bw
        if grps:
            groups_by_class[cls] = grps
    return flat, groups_by_class
