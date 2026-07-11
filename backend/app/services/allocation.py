"""Divisão do aporte entre os ativos ranqueados (v2).

Melhorias sobre a v1 (ver ANALISE-V2.md):
1. Orçamento por classe é NEED-BASED sobre a carteira RESULTANTE:
   need = max(0, alvo·(total+aporte) − valor_atual_da_classe). Corrige a sobre-correção
   quando o aporte é grande em relação à carteira.
2. SLOTS de max_assets distribuídos POR CLASSE (maior-resto/Hamilton), garantindo ≥1 por
   classe com orçamento — elimina o viés do contador global que dava todos os slots à 1ª classe.
3. SEGUNDA PASSADA: a sobra de arredondamento de lote é reaproveitada comprando +1 lote nos
   ativos já escolhidos (por ordem de score), minimizando o `unallocated` sem furar os tetos.
4. Lote inteiro respeitado (o tamanho real do lote vem do Asset/serviço de mercado).
"""
from __future__ import annotations

from typing import Dict, List

from app.models.portfolio import Portfolio
from app.models.scoring import ScoredAsset, SuggestedBuy


def _distribute_slots(class_budget: Dict[str, float], max_assets: int) -> Dict[str, int]:
    """Distribui `max_assets` slots entre as classes proporcional ao orçamento (maior-resto),
    garantindo ao menos 1 slot para cada classe com orçamento positivo (quando couber)."""
    classes = [c for c, b in class_budget.items() if b > 0]
    if not classes:
        return {}
    total = sum(class_budget[c] for c in classes)
    if total <= 0:
        return {c: 1 for c in classes[:max_assets]}

    # piso de 1 por classe com orçamento, respeitando o teto global de max_assets
    base = {c: 1 for c in classes}
    if len(classes) > max_assets:
        # mais classes que slots: prioriza as de maior orçamento
        ordered = sorted(classes, key=lambda c: class_budget[c], reverse=True)[:max_assets]
        return {c: 1 for c in ordered}

    remaining = max_assets - len(classes)
    if remaining <= 0:
        return base

    # distribui o restante pelos maiores restos (Hamilton)
    quotas = {c: remaining * (class_budget[c] / total) for c in classes}
    floors = {c: int(q) for c, q in quotas.items()}
    assigned = sum(floors.values())
    leftover = remaining - assigned
    remainders = sorted(classes, key=lambda c: quotas[c] - floors[c], reverse=True)
    for c in remainders[:leftover]:
        floors[c] += 1
    return {c: base[c] + floors[c] for c in classes}


def _allocate_basket(
    basket: Dict[str, float],
    budget: float,
    asset_class: str,
    rank_by_ticker: Dict[str, ScoredAsset],
    prices: Dict[str, float],
    lot_sizes: Dict[str, int],
    held: Dict[str, float],
    min_ticket: float,
    chosen: Dict[str, int],
    target_amounts: Dict[str, float],
    spent_by_class: Dict[str, float],
) -> float:
    """Aloca o orçamento de uma classe pela carteira alvo do usuário (cesta de pesos).

    Compra proporcional ao DÉFICIT de cada ticker (peso-alvo × total resultante da cesta
    − valor atual), não ao score: quem está mais longe do alvo recebe mais. Ticker acima
    do alvo recebe 0. Sem teto por ativo nem limite de slots — os pesos da cesta são a
    vontade explícita do usuário; `min_ticket` e lote continuam valendo. Posições da
    classe fora da cesta não entram na conta. Retorna quanto foi gasto.
    """
    members = {
        t: w
        for t, w in basket.items()
        if t in rank_by_ticker and (prices.get(t) or 0) > 0
    }
    if not members:
        return 0.0
    wsum = sum(members.values())
    share_target = {t: w / wsum for t, w in members.items()}  # renormaliza sem os sem-preço
    cur = {t: held.get(t, 0.0) for t in members}
    basket_total = sum(cur.values()) + budget
    deficit = {t: max(0.0, share_target[t] * basket_total - cur[t]) for t in members}
    dsum = sum(deficit.values())
    # cesta já no alvo (só sobra proporcional): rateia pelos próprios pesos
    amounts = (
        {t: budget * share_target[t] for t in members}
        if dsum <= 0
        else {t: budget * deficit[t] / dsum for t in members}
    )

    def lot_of(ticker: str) -> int:
        return max(1, lot_sizes.get(ticker, 1))

    spent = 0.0
    for t, amount in amounts.items():
        if amount < min_ticket:
            continue
        price = prices.get(t) or 0.0
        lot = lot_of(t)
        shares = int(amount // (price * lot)) * lot
        if shares <= 0:
            continue
        invested = shares * price
        chosen[t] = chosen.get(t, 0) + shares
        target_amounts[t] = round(amount, 2)
        spent += invested
        spent_by_class[asset_class] = spent_by_class.get(asset_class, 0.0) + invested

    # segunda passada local: +1 lote por vez no MAIOR déficit restante que caiba na sobra
    # da classe (não inicia posições puladas pelo min_ticket, como na passada global)
    def remaining(t: str) -> float:
        return share_target[t] * basket_total - (cur[t] + chosen[t] * (prices.get(t) or 0.0))

    leftover = budget - spent
    progress = True
    while progress:
        progress = False
        for t in sorted((t for t in members if t in chosen), key=remaining, reverse=True):
            price = prices.get(t) or 0.0
            cost = price * lot_of(t)
            if cost <= 0 or cost > leftover or remaining(t) <= 0:
                continue
            chosen[t] += lot_of(t)
            spent += cost
            spent_by_class[asset_class] += cost
            leftover -= cost
            progress = True
            break  # reordena pelos déficits atualizados
    return spent


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
    max_weight_per_class: float | None = None,
    class_baskets: Dict[str, Dict[str, float]] | None = None,
) -> float:
    """Preenche `suggested` nos ativos selecionados. Retorna o valor não alocado (sobra).

    `class_baskets` ({classe: {ticker: peso}}) troca o split por score da classe pela
    matemática de rebalanceamento da cesta: comprar o que está mais longe do peso-alvo.
    """
    if aporte <= 0 or not ranking:
        return aporte

    total_after = portfolio.total_value + aporte
    cur_weight = portfolio.allocations.by_class
    cur_value = {c: cur_weight.get(c, 0.0) * portfolio.total_value for c in cur_weight}
    held = {p.ticker: p.value for p in portfolio.positions}
    baskets = {c: b for c, b in (class_baskets or {}).items() if b}
    rank_by_ticker = {r.ticker: r for r in ranking}

    def priced(r: ScoredAsset) -> bool:
        return (prices.get(r.ticker) or 0) > 0 and r.composite_score > 0

    def buyable(r: ScoredAsset) -> bool:
        # cesta: basta ter preço — a compra vem do desvio ao alvo, não do score
        if r.asset_class in baskets:
            return r.ticker in baskets[r.asset_class] and (prices.get(r.ticker) or 0) > 0
        return priced(r)

    investable = {r.asset_class for r in ranking if buyable(r)}
    if not investable:
        return round(aporte, 2)

    # 1) orçamento por classe, NEED-BASED sobre a carteira resultante
    needs = {
        c: max(0.0, targets.get(c, 0.0) * total_after - cur_value.get(c, 0.0)) for c in investable
    }
    total_need = sum(needs.values())
    if total_need > 0:
        class_budget = {c: aporte * (needs[c] / total_need) for c in investable}
    else:
        # já no/acima do alvo em todas as classes investíveis: rateia pelos próprios alvos
        base = {c: targets.get(c, 0.0) for c in investable}
        s = sum(base.values()) or 1.0
        class_budget = {c: aporte * (base[c] / s) for c in investable}

    # 2) slots por classe — cestas não consomem slots: nelas o nº de ativos é decidido
    #    pelos pesos do próprio usuário (max_assets não se aplica)
    slots = _distribute_slots(
        {c: b for c, b in class_budget.items() if c not in baskets}, max_assets
    )

    chosen: Dict[str, int] = {}  # ticker -> shares
    target_amounts: Dict[str, float] = {}
    spent = 0.0
    spent_by_class: Dict[str, float] = {c: 0.0 for c in investable}

    def lot_of(ticker: str) -> int:
        return max(1, lot_sizes.get(ticker, 1))

    def asset_cap_room(r: ScoredAsset) -> float:
        cap = max_weight_per_asset * total_after
        already = chosen.get(r.ticker, 0) * (prices.get(r.ticker) or 0.0)
        return max(0.0, cap - held.get(r.ticker, 0.0) - already)

    def class_cap_room(c: str) -> float:
        if max_weight_per_class is None:
            return float("inf")
        cap = max_weight_per_class * total_after
        return max(0.0, cap - cur_value.get(c, 0.0) - spent_by_class.get(c, 0.0))

    # 3) primeira passada: cesta (desvio ao alvo) ou, sem cesta, proporcional ao score
    for c in sorted(class_budget, key=lambda x: class_budget[x], reverse=True):
        budget = class_budget[c]
        if budget <= 0:
            continue
        if c in baskets:
            spent += _allocate_basket(
                basket=baskets[c],
                budget=budget,
                asset_class=c,
                rank_by_ticker=rank_by_ticker,
                prices=prices,
                lot_sizes=lot_sizes,
                held=held,
                min_ticket=min_ticket,
                chosen=chosen,
                target_amounts=target_amounts,
                spent_by_class=spent_by_class,
            )
            continue
        n_slots = slots.get(c, 0)
        if n_slots <= 0:
            continue
        in_class = [r for r in ranking if r.asset_class == c and priced(r)][:n_slots]
        score_sum = sum(r.composite_score for r in in_class) or 1.0
        for r in in_class:
            target_amount = budget * (r.composite_score / score_sum)
            target_amount = min(target_amount, asset_cap_room(r), class_cap_room(c))
            if target_amount < min_ticket:
                continue
            price = prices.get(r.ticker) or 0.0
            lot = lot_of(r.ticker)
            if price <= 0:
                continue
            shares = int(target_amount // (price * lot)) * lot
            if shares <= 0:
                continue
            invested = shares * price
            chosen[r.ticker] = shares
            target_amounts[r.ticker] = round(target_amount, 2)
            spent += invested
            spent_by_class[c] += invested

    # 4) segunda passada: reaproveita a sobra comprando +1 lote nos ativos JÁ escolhidos
    #    (não inicia posições puladas por min_ticket — esse é um piso para abrir posição).
    #    Tickers de cesta ficam de fora: o complemento deles é local (por déficit), e
    #    estourar o alvo da cesta com sobra de outra classe contraria o pedido do usuário.
    basket_tickers = {t for b in baskets.values() for t in b}
    progress = True
    while progress:
        progress = False
        leftover = aporte - spent
        chosen_sorted = sorted(
            (t for t in chosen if t not in basket_tickers),
            key=lambda t: rank_by_ticker[t].composite_score,
            reverse=True,
        )
        for ticker in chosen_sorted:
            r = rank_by_ticker[ticker]
            price = prices.get(ticker) or 0.0
            lot = lot_of(ticker)
            cost = price * lot
            if cost <= 0 or cost > leftover:
                continue
            if cost > asset_cap_room(r) or cost > class_cap_room(r.asset_class):
                continue
            chosen[ticker] += lot
            spent += cost
            spent_by_class[r.asset_class] += cost
            leftover -= cost
            progress = True

    # 5) grava as sugestões
    for r in ranking:
        shares = chosen.get(r.ticker)
        if not shares:
            continue
        price = prices.get(r.ticker) or 0.0
        lot = lot_of(r.ticker)
        r.suggested = SuggestedBuy(
            target_amount=target_amounts.get(r.ticker, round(shares * price, 2)),
            price=price or None,
            shares=shares,
            invested_exact=round(shares * price, 2),
            lot_size=lot,
            lot_note=f"lote {lot}" if lot > 1 else None,
        )

    return round(max(0.0, aporte - spent), 2)
