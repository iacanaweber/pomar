"""Divisão do aporte entre os ativos da carteira alvo — rebalanceamento puro.

Não existe score aqui (nem em lugar nenhum): o que decide quanto vai para cada ativo é a
DISTÂNCIA até o peso que o usuário definiu. Em três passadas:

1. **Entre as classes** marcadas, o orçamento é NEED-BASED sobre a carteira resultante:
   `need_c = max(0, alvo_c·(total+aporte) − valor_alinhado_c)`. Os alvos entram CRUS (sem
   renormalizar entre as classes selecionadas): a proporção entre os needs já se
   normaliza sozinha, e renormalizar faria a classe escolhida perseguir um alvo que não
   é o dela — sobre-correção.
   `valor_alinhado_c` conta só os membros da cesta: uma posição fora do alvo não é
   progresso rumo ao alvo (ver `aligned_value_by_class`).
2. **Dentro da classe**, cada ativo da cesta recebe proporcionalmente ao seu déficit
   (peso-alvo × total resultante da cesta − valor atual). Quem está no alvo ou acima
   recebe zero. `min_ticket` vale para ABRIR posição; lote inteiro é sempre respeitado.
3. **Sobra global**: o troco de arredondamento de lote de todas as classes é reunido e
   compra +1 lote por vez de quem estiver mais longe do alvo GLOBAL em R$ (meta da
   classe × peso na cesta), recalculado a cada compra — é o que permite ao troco de uma
   classe completar um lote em outra.

Invariante: `spent + unallocated == aporte`.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.models.plan import PlanAsset, SuggestedBuy
from app.models.portfolio import Portfolio


def _allocate_basket(
    basket: Dict[str, float],
    budget: float,
    asset_class: str,
    prices: Dict[str, float],
    lot_sizes: Dict[str, int],
    held: Dict[str, float],
    min_ticket: float,
    chosen: Dict[str, int],
    target_amounts: Dict[str, float],
    spent_by_class: Dict[str, float],
) -> float:
    """Aloca o orçamento de uma classe pela cesta de pesos-alvo do usuário.

    Compra proporcional ao DÉFICIT de cada ticker (peso-alvo × total resultante da cesta
    − valor atual): quem está mais longe do alvo recebe mais; quem está acima recebe 0.
    Sem teto por ativo e sem limite de quantos ativos entram — os pesos da cesta são a
    vontade explícita do usuário. Posições da classe fora da cesta não entram na conta.
    Retorna quanto foi gasto.
    """
    members = _priced_members(basket, prices)
    if not members:
        return 0.0
    share_target = _share_target(members)
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
    # da classe (não inicia posições puladas pelo min_ticket — isso é da passada global)
    def remaining(t: str) -> float:
        return share_target[t] * basket_total - (cur[t] + chosen.get(t, 0) * (prices.get(t) or 0.0))

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


def _priced_members(basket: Dict[str, float], prices: Dict[str, float]) -> Dict[str, float]:
    """Membros da cesta com cotação — sem preço não há como calcular quantas cotas comprar."""
    return {t: w for t, w in basket.items() if (prices.get(t) or 0) > 0}


def _share_target(members: Dict[str, float]) -> Dict[str, float]:
    """Pesos renormalizados entre os membros que sobraram (soma 1)."""
    wsum = sum(members.values()) or 1.0
    return {t: w / wsum for t, w in members.items()}


def aligned_value_by_class(
    held: Dict[str, float],
    class_baskets: Optional[Dict[str, Dict[str, float]]],
    targets: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """Valor de cada classe que de fato SEGUE a carteira alvo (o legado fica de fora).

    A alternativa — somar tudo que é da classe, como faz `allocations.by_class` — faz o
    legado se cancelar: ele infla a base do alvo e o valor atual na mesma medida, e a
    classe parece já estar no lugar. Contar só os membros da cesta é o que torna o `need`
    sensível ao capital que está de saída.

    Usa a cesta DECLARADA (não a filtrada por preço): um ticker do alvo cuja cotação falhou
    continua sendo capital alinhado — a falha é do provedor, não uma decisão de estratégia.
    """
    alvos = targets or {}
    out: Dict[str, float] = {}
    for c, basket in (class_baskets or {}).items():
        if not basket or alvos.get(c, 0.0) <= 0:
            continue
        out[c] = sum(held.get(t, 0.0) for t, w in basket.items() if (w or 0) > 0)
    return out


def allocate(
    aporte: float,
    ranking: List[PlanAsset],
    portfolio: Portfolio,
    prices: Dict[str, float],
    lot_sizes: Dict[str, int],
    targets: Dict[str, float],
    class_baskets: Dict[str, Dict[str, float]],
    min_ticket: float = 100.0,
    legacy_in_total: bool = True,
    extra_base: float = 0.0,
) -> float:
    """Preenche `suggested` e os campos `basket_*` do ranking. Retorna a sobra não alocada.

    `legacy_in_total` decide a BASE dos alvos em R$: com `True` (default), o valor das
    posições fora da carteira alvo entra no patrimônio sobre o qual as metas são
    aplicadas. Isso aumenta o `need` das classes-alvo e mantém a carteira subalocada até a
    venda — o retrato aritmeticamente honesto de quem ainda tem capital fora da
    estratégia. Com `False`, as metas incidem só sobre o capital alinhado.

    `extra_base` é o patrimônio que existe FORA das posições de renda variável — hoje, a
    renda fixa que conta na carteira. Sem ele, uma carteira 30% em Tesouro Selic miraria
    alvos calculados como se aquele dinheiro não existisse, e a bolsa pediria aporte a mais.
    """
    by_ticker = {r.ticker: r for r in ranking}
    baskets = {
        c: m
        for c, b in (class_baskets or {}).items()
        if (m := _priced_members({t: w for t, w in b.items() if t in by_ticker}, prices))
    }
    if not baskets:
        return round(max(0.0, aporte), 2)

    held = {p.ticker: p.value for p in portfolio.positions}
    chosen: Dict[str, int] = {}  # ticker -> cotas a comprar
    target_amounts: Dict[str, float] = {}
    spent_by_class: Dict[str, float] = {c: 0.0 for c in baskets}
    spent = 0.0

    if aporte > 0:
        # 1) orçamento por classe, NEED-BASED sobre a carteira resultante
        cur_value = aligned_value_by_class(held, class_baskets, targets)
        base = portfolio.total_value if legacy_in_total else sum(cur_value.values())
        total_after = base + max(0.0, extra_base) + aporte
        needs = {
            c: max(0.0, targets.get(c, 0.0) * total_after - cur_value.get(c, 0.0)) for c in baskets
        }
        total_need = sum(needs.values())
        if total_need > 0:
            class_budget = {c: aporte * (needs[c] / total_need) for c in baskets}
        else:
            # já no/acima do alvo em todas as classes marcadas: rateia pelos próprios alvos
            base = {c: targets.get(c, 0.0) for c in baskets}
            s = sum(base.values())
            class_budget = (
                {c: aporte * (base[c] / s) for c in baskets}
                if s > 0
                else {c: 0.0 for c in baskets}
            )

        # 2) dentro de cada classe: compra por déficit ao peso-alvo da cesta
        for c in sorted(class_budget, key=lambda x: class_budget[x], reverse=True):
            if class_budget[c] <= 0:
                continue
            spent += _allocate_basket(
                basket=baskets[c],
                budget=class_budget[c],
                asset_class=c,
                prices=prices,
                lot_sizes=lot_sizes,
                held=held,
                min_ticket=min_ticket,
                chosen=chosen,
                target_amounts=target_amounts,
                spent_by_class=spent_by_class,
            )

        # 3) sobra global: o troco de lote de TODAS as classes compra +1 lote de quem
        #    estiver mais longe do alvo em R$, em qualquer cesta
        spent += _spend_leftover(
            aporte - spent, baskets, targets, prices, lot_sizes, held, chosen, min_ticket
        )

    _fill_basket_view(ranking, baskets, prices, held, chosen)

    for r in ranking:
        shares = chosen.get(r.ticker)
        if not shares:
            continue
        price = prices.get(r.ticker) or 0.0
        lot = max(1, lot_sizes.get(r.ticker, 1))
        r.suggested = SuggestedBuy(
            target_amount=target_amounts.get(r.ticker, round(shares * price, 2)),
            price=price or None,
            shares=shares,
            invested_exact=round(shares * price, 2),
            lot_size=lot,
            lot_note=f"lote {lot}" if lot > 1 else None,
        )

    return round(max(0.0, aporte - spent), 2)


def _spend_leftover(
    leftover: float,
    baskets: Dict[str, Dict[str, float]],
    targets: Dict[str, float],
    prices: Dict[str, float],
    lot_sizes: Dict[str, int],
    held: Dict[str, float],
    chosen: Dict[str, int],
    min_ticket: float,
) -> float:
    """Gasta o troco comprando 1 lote por vez de quem está mais longe do alvo GLOBAL.

    O alvo global de um ticker é `meta da classe (renormalizada entre as marcadas) × peso
    dele na cesta`, aplicado ao valor que a carteira alvo terá com a sobra toda investida.
    Uma única régua em R$ resolve o desequilíbrio dentro e entre as cestas — e continua
    valendo quando a cesta tem um ativo só (medir o déficit contra a própria cesta daria
    zero por construção, e o troco nunca seria investido).

    Dois guarda-corpos: só compra quem ainda está ABAIXO do alvo (o overshoot fica
    limitado a um lote) e só abre posição nova quando o lote custa pelo menos
    `min_ticket` — o piso existe para não pulverizar o aporte em pontas.
    """
    class_of = {t: c for c, m in baskets.items() for t in m}
    tsum = sum(max(0.0, targets.get(c, 0.0)) for c in baskets)
    if tsum <= 0 or leftover <= 0:
        return 0.0
    share_global = {
        t: (max(0.0, targets.get(c, 0.0)) / tsum) * w
        for c, m in baskets.items()
        for t, w in _share_target(m).items()
    }

    def value_now(t: str) -> float:
        return held.get(t, 0.0) + chosen.get(t, 0) * (prices.get(t) or 0.0)

    def remaining(t: str) -> float:
        total_after = sum(value_now(x) for x in class_of) + leftover
        return share_global[t] * total_after - value_now(t)

    spent = 0.0
    progress = True
    while progress:
        progress = False
        for t in sorted(class_of, key=remaining, reverse=True):
            lot = max(1, lot_sizes.get(t, 1))
            cost = (prices.get(t) or 0.0) * lot
            if cost <= 0 or cost > leftover or remaining(t) <= 0:
                continue
            if value_now(t) <= 0 and cost < min_ticket:
                continue  # abrir posição nova exige o ticket mínimo
            chosen[t] = chosen.get(t, 0) + lot
            spent += cost
            leftover -= cost
            progress = True
            break  # reordena pelos déficits atualizados
    return spent


def _fill_basket_view(
    ranking: List[PlanAsset],
    baskets: Dict[str, Dict[str, float]],
    prices: Dict[str, float],
    held: Dict[str, float],
    chosen: Dict[str, int],
) -> None:
    """Grava no ranking a posição de cada ativo na cesta: alvo, hoje, depois e o gap em R$.

    Calculado aqui (e não na rota) porque só o alocador conhece o resultado final das três
    passadas — recalcular do lado de fora divergiria do que foi de fato comprado.
    """
    by_ticker = {r.ticker: r for r in ranking}
    for c, members in baskets.items():
        share_target = _share_target(members)
        cur = {t: held.get(t, 0.0) for t in members}
        after = {t: cur[t] + chosen.get(t, 0) * (prices.get(t) or 0.0) for t in members}
        v_cur = sum(cur.values())
        v_after = sum(after.values())
        for t in members:
            r = by_ticker.get(t)
            if r is None:
                continue
            r.basket_target_pct = round(share_target[t], 6)
            r.basket_current_pct = round(cur[t] / v_cur, 6) if v_cur > 0 else 0.0
            r.basket_after_pct = round(after[t] / v_after, 6) if v_after > 0 else 0.0
            # gap medido sobre a cesta JÁ com o aporte — é o número que gerou a compra
            r.basket_gap_brl = round(share_target[t] * v_after - cur[t], 2)


def basket_classes(class_baskets: Optional[Dict[str, Dict[str, float]]]) -> List[str]:
    """Classes que têm composição definida (cesta não vazia), em ordem alfabética."""
    return sorted(c for c, b in (class_baskets or {}).items() if b)
