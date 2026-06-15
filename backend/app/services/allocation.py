"""Divisão do aporte entre os ativos ranqueados.

Estratégia (orientada à meta, não só ao score):
1. Distribui o aporte entre CLASSES proporcional ao gap de rebalanceamento (o que está
   mais abaixo do alvo recebe mais), respeitando os alvos.
2. Dentro de cada classe, distribui aos melhores ranqueados proporcional ao score,
   respeitando max_assets e max_weight_per_asset.
3. Arredonda para nº inteiro de cotas pelo preço; a sobra vira `unallocated`.
"""
from __future__ import annotations

from typing import Dict, List

from app.models.portfolio import Portfolio
from app.models.scoring import ScoredAsset, SuggestedBuy


def _class_budget(
    aporte: float, targets: Dict[str, float], portfolio: Portfolio, classes_present: set
) -> Dict[str, float]:
    """Quanto do aporte vai para cada classe, proporcional ao gap até o alvo."""
    current = portfolio.allocations.by_class
    gaps = {}
    for cls in classes_present:
        gap = max(0.0, targets.get(cls, 0.0) - current.get(cls, 0.0))
        gaps[cls] = gap
    total = sum(gaps.values())
    if total <= 0:
        # já no alvo (ou acima): divide proporcional aos próprios alvos das classes presentes
        base = {c: targets.get(c, 0.0) for c in classes_present}
        s = sum(base.values()) or 1.0
        return {c: aporte * (v / s) for c, v in base.items()}
    return {cls: aporte * (gap / total) for cls, gap in gaps.items()}


def allocate(
    aporte: float,
    ranking: List[ScoredAsset],
    portfolio: Portfolio,
    prices: Dict[str, float],
    lot_sizes: Dict[str, int],
    targets: Dict[str, float],
    max_assets: int = 5,
    max_weight_per_asset: float = 0.20,
    min_ticket: float = 100.0,
) -> float:
    """Preenche `suggested` nos ativos selecionados. Retorna o valor não alocado (sobra)."""
    if aporte <= 0 or not ranking:
        return aporte

    classes_present = {r.asset_class for r in ranking}
    class_budget = _class_budget(aporte, targets, portfolio, classes_present)
    total_after = portfolio.total_value + aporte

    spent = 0.0
    chosen = 0
    for cls in sorted(class_budget, key=lambda c: class_budget[c], reverse=True):
        budget = class_budget[cls]
        if budget <= 0:
            continue
        # melhores ativos da classe
        in_class = [r for r in ranking if r.asset_class == cls and r.composite_score > 0]
        in_class = in_class[: max(1, max_assets - chosen)]
        score_sum = sum(r.composite_score for r in in_class) or 1.0
        for r in in_class:
            if chosen >= max_assets:
                break
            target_amount = budget * (r.composite_score / score_sum)
            # teto de concentração sobre a carteira resultante
            cap_value = max_weight_per_asset * total_after
            held = next((p.value for p in portfolio.positions if p.ticker == r.ticker), 0.0)
            target_amount = min(target_amount, max(0.0, cap_value - held))
            if target_amount < min_ticket:
                continue
            price = prices.get(r.ticker) or 0.0
            lot = max(1, lot_sizes.get(r.ticker, 1))
            if price > 0:
                shares = int(target_amount // (price * lot)) * lot
                invested = shares * price
            else:
                shares = 0
                invested = 0.0
            if shares <= 0:
                continue
            r.suggested = SuggestedBuy(
                target_amount=round(target_amount, 2),
                price=price or None,
                shares=shares,
                invested_exact=round(invested, 2),
                lot_size=lot,
                lot_note=f"lote {lot}" if lot > 1 else None,
            )
            spent += invested
            chosen += 1

    return round(max(0.0, aporte - spent), 2)
