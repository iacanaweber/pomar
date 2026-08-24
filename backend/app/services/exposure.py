"""Composição do patrimônio por dimensão — renda variável MAIS a renda fixa que conta.

Enquanto a renda fixa vivia só na aba Reserva, "composição da carteira" e "composição da
renda variável" eram a mesma coisa. Deixaram de ser: uma conta marcada como parte do
patrimônio precisa aparecer nos gráficos, senão o app mostra uma carteira 100% em bolsa
para quem tem 30% em Tesouro Selic.

Três dimensões saem daqui:

* **class** — a mesma classe que dirige a compra, com `RENDA_FIXA` incluindo os saldos.
* **sector** — o setor do ativo; as contas de renda fixa entram como "Renda fixa".
* **geography** — domicílio do ativo, com os rótulos do usuário quando existem e o mapa
  curado de `data/geography.py` como default. Exposição parcial é respeitada: um ETF 60%
  internacional soma 60% do seu valor em INTL e 40% em BR.

Função pura sobre listas de dicts; somas em centavos inteiros.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.data import geography
from app.util import from_cents, to_cents

RENDA_FIXA = "RENDA_FIXA"
SETOR_RENDA_FIXA = "Renda fixa"

# Contas de renda fixa sem rótulo próprio são brasileiras: CDB, Tesouro e LCI são
# instrumentos daqui. O usuário pode sobrescrever, como em qualquer outro rótulo.
GEOGRAFIA_PADRAO_CONTA = "BR"


def _split(value: float, labels: Optional[List[Dict[str, Any]]], fallback: str) -> Dict[str, int]:
    """Rateia um valor entre os rótulos do sujeito, em centavos. Sem rótulo, vai inteiro
    para o `fallback`. O resíduo fica na maior fatia, para as partes somarem o todo."""
    cents = to_cents(value)
    if cents == 0:
        return {}
    if not labels:
        return {fallback: cents}
    partes = {lab["code"]: int(cents * float(lab.get("weight", 1.0))) for lab in labels}
    sobra = cents - sum(partes.values())
    if sobra:
        partes[max(partes, key=lambda code: partes[code])] += sobra
    return partes


def compose(
    positions: Iterable[Dict[str, Any]],
    rf_accounts: Iterable[Dict[str, Any]] = (),
    geography_by_ticker: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    geography_by_account: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """{'total', 'by_class', 'by_sector', 'by_geography'} em reais.

    `positions` são as posições de renda variável já classificadas (ticker, asset_class,
    sector, value); `rf_accounts` são as contas que contam na carteira, com `balance`.
    """
    total = 0
    valores: Dict[str, Dict[str, int]] = {"class": {}, "sector": {}, "geography": {}}
    membros: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        "class": {}, "sector": {}, "geography": {}
    }

    def somar(dim: str, chave: str, cents: int, rotulo: str, nome: Optional[str]) -> None:
        valores[dim][chave] = valores[dim].get(chave, 0) + cents
        membros[dim].setdefault(chave, []).append(
            {"label": rotulo, "name": nome, "value": from_cents(cents)}
        )

    for p in positions:
        cents = to_cents(p.get("value", 0.0))
        if cents == 0:
            continue
        total += cents
        ticker = str(p.get("ticker", "")).upper()
        nome = p.get("name")
        somar("class", p.get("asset_class") or "UNKNOWN", cents, ticker, nome)
        somar("sector", p.get("sector") or "Sem setor", cents, ticker, nome)
        for code, parte in _split(
            p.get("value", 0.0),
            (geography_by_ticker or {}).get(ticker),
            geography.default_geography(ticker),
        ).items():
            somar("geography", code, parte, ticker, nome)

    for acc in rf_accounts:
        cents = to_cents(acc.get("balance", 0.0))
        if cents == 0:
            continue
        total += cents
        rotulo = str(acc.get("name") or f"Conta {acc.get('id')}")
        somar("class", RENDA_FIXA, cents, rotulo, acc.get("institution"))
        somar("sector", SETOR_RENDA_FIXA, cents, rotulo, acc.get("institution"))
        for code, parte in _split(
            acc.get("balance", 0.0),
            (geography_by_account or {}).get(str(acc.get("id"))),
            GEOGRAFIA_PADRAO_CONTA,
        ).items():
            somar("geography", code, parte, rotulo, acc.get("institution"))

    def reais(d: Dict[str, int]) -> Dict[str, float]:
        return {k: from_cents(v) for k, v in d.items() if v}

    return {
        "total": from_cents(total),
        "by_class": reais(valores["class"]),
        "by_sector": reais(valores["sector"]),
        "by_geography": reais(valores["geography"]),
        "members": membros,
    }


def with_targets(
    values: Dict[str, float],
    total: float,
    targets: Optional[Dict[str, float]] = None,
    members: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> List[Dict[str, Any]]:
    """Transforma {código: valor} em itens com fatia, meta e desvio em pontos percentuais.

    A meta é OPCIONAL e informativa: nenhuma decisão de compra passa por aqui. Códigos com
    meta e sem valor aparecem mesmo assim — uma exposição planejada e ainda não montada é
    informação, e filtrá-la esconderia justamente o desvio que interessa.
    """
    alvos = {k: float(v) for k, v in (targets or {}).items() if v}
    saida: List[Dict[str, Any]] = []
    for code in sorted(set(values) | set(alvos)):
        valor = values.get(code, 0.0)
        pct = round(valor / total, 6) if total > 0 else 0.0
        alvo = alvos.get(code)
        saida.append({
            "code": code,
            "value": valor,
            "pct": pct,
            "target_pct": alvo,
            "deviation_pp": round((pct - alvo) * 100, 2) if alvo is not None else None,
            "members": sorted(
                (members or {}).get(code, []), key=lambda m: m["value"], reverse=True
            ),
        })
    return sorted(saida, key=lambda i: (-i["value"], i["code"]))
