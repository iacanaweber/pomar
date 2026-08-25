"""Valor da carteira por TAG DE INDEXADOR — os itens da cesta de `RENDA_FIXA`.

Nas outras classes o item da cesta é um ticker; em `RENDA_FIXA` é o indexador (CDI, IPCA,
LCI…). O valor de uma tag é a soma dos saldos das contas com aquela tag MAIS o valor das
posições de renda variável atribuídas a ela — é isso que permite um ETF de renda fixa
(IMAB11, IRFM11) pesar na cesta ao lado de um CDB, que é como o dono da carteira pensa.

Uma conta pode ter mais de uma tag: o saldo é rateado pelos pesos da atribuição (que somam
1.0 por dimensão, garantido em `labels_repo`). Conta que conta na carteira e não tem tag
alguma não some: cai no bucket residual `SEM_INDEXADOR`, visível na tela. Um bucket
residual silencioso seria pior que um errado — o dinheiro sumiria da composição sem que
nada avisasse.

Função pura sobre listas de dicts, como o resto de `services/`. Somas em centavos inteiros.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.data.labels_seed import NO_INDEXER_CODE
from app.util import from_cents, looks_like_ticker, to_cents


def _split(value: float, labels: Optional[List[Dict[str, Any]]]) -> Dict[str, int]:
    """Rateia um valor entre as tags do sujeito, em centavos. Sem tag => residual.

    O resíduo do rateio vai para a MAIOR fatia, para a soma das partes bater com o todo:
    R$100 em três tags de 1/3 são 33,33 + 33,33 + 33,34, nunca 99,99.
    """
    cents = to_cents(value)
    if not labels:
        return {NO_INDEXER_CODE: cents} if cents else {}
    if cents == 0:
        return {}
    partes = {lab["code"]: int(cents * float(lab.get("weight", 1.0))) for lab in labels}
    sobra = cents - sum(partes.values())
    if sobra:
        maior = max(partes, key=lambda code: partes[code])
        partes[maior] += sobra
    return partes


def value_by_indexer(
    accounts: Iterable[Dict[str, Any]],
    account_labels: Dict[str, List[Dict[str, Any]]],
    positions: Iterable[Dict[str, Any]] = (),
    ticker_labels: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    basket_tickers: Iterable[str] = (),
) -> Dict[str, float]:
    """{código do item da cesta: valor em R$}.

    `accounts` já vem filtrado por quem conta na carteira (ver `fixed_income_repo.balances`
    + `counts_in_portfolio`); `positions` são as posições de renda variável cujo bucket é
    `RENDA_FIXA`. As chaves de `account_labels` são ids de conta como texto, as de
    `ticker_labels` são tickers normalizados — a mesma convenção de `label_assignments`.

    `basket_tickers` são os tickers que são ITEM PRÓPRIO da cesta (IMAB11 declarado em
    `class_targets["RENDA_FIXA"]`). O valor deles vai para o código do próprio ticker e
    NÃO é rateado pela tag de indexador: somar as duas coisas contaria o mesmo dinheiro
    duas vezes dentro da mesma cesta, e a soma dos itens passaria do total da classe.
    Vazio — o default — reproduz exatamente o comportamento de sempre.
    """
    proprios = {str(t).strip().upper() for t in (basket_tickers or ())}
    total: Dict[str, int] = {}

    def somar(partes: Dict[str, int]) -> None:
        for code, cents in partes.items():
            total[code] = total.get(code, 0) + cents

    for acc in accounts:
        somar(_split(acc.get("balance", 0.0), account_labels.get(str(acc["id"]))))
    for pos in positions:
        ticker = str(pos.get("ticker", "")).upper()
        if ticker in proprios:
            cents = to_cents(pos.get("value", 0.0))
            if cents:
                somar({ticker: cents})
            continue
        somar(_split(pos.get("value", 0.0), (ticker_labels or {}).get(ticker)))

    return {code: from_cents(cents) for code, cents in total.items() if cents}


def split_basket(
    basket: Optional[Dict[str, float]]
) -> tuple[Dict[str, float], Dict[str, float]]:
    """(tags, tickers) — a cesta de renda fixa partida pelo TIPO do item, pesos intactos.

    Os dois tipos disputam o mesmo orçamento pela mesma régua de déficit; o que muda é
    COMO o dinheiro entra: a tag por lançamento em conta, em qualquer valor; o ticker por
    compra de cotas, com lote e ticket mínimo.
    """
    tags: Dict[str, float] = {}
    tickers: Dict[str, float] = {}
    for code, peso in (basket or {}).items():
        chave = str(code).strip().upper()
        (tickers if looks_like_ticker(chave) else tags)[chave] = float(peso)
    return tags, tickers


def basket_deficits(
    target_weights: Dict[str, float], current: Dict[str, float], budget: float
) -> Dict[str, float]:
    """Rateia um orçamento entre as tags proporcionalmente ao DÉFICIT de cada uma.

    Mesma aritmética de `allocation._allocate_basket`: quem está mais longe do peso-alvo
    recebe mais, quem está no alvo ou acima recebe zero. Cesta inteira no alvo (só sobra
    proporcional) rateia pelos próprios pesos, para o dinheiro não ficar parado.

    Sem lote nem ticket mínimo: a compra de renda fixa é manual e aceita qualquer valor.
    """
    if budget <= 0 or not target_weights:
        return {}
    peso_total = sum(w for w in target_weights.values() if w > 0) or 1.0
    alvo = {c: max(0.0, w) / peso_total for c, w in target_weights.items()}
    base = sum(to_cents(v) for c, v in current.items() if c in alvo) + to_cents(budget)
    deficit = {c: max(0, int(alvo[c] * base) - to_cents(current.get(c, 0.0))) for c in alvo}
    soma = sum(deficit.values())
    pesos = deficit if soma > 0 else {c: int(alvo[c] * 1_000_000) for c in alvo}
    soma = sum(pesos.values()) or 1

    orcamento = to_cents(budget)
    saida = {c: orcamento * p // soma for c, p in pesos.items() if p > 0}
    resto = orcamento - sum(saida.values())
    if resto and saida:
        maior = max(saida, key=lambda c: saida[c])
        saida[maior] += resto
    return {c: from_cents(v) for c, v in saida.items() if v > 0}
