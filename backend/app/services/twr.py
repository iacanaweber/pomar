"""Retorno da carteira — tempo-ponderado (TWR) e dinheiro-ponderado (XIRR). Puro.

**Por que não basta plotar o valor da carteira.** O patrimônio cresce por aporte, não só
por rentabilidade. Sem neutralizar os fluxos, qualquer carteira que recebe aporte "bate o
Ibovespa" e o gráfico não significa nada. As duas medidas abaixo respondem perguntas
diferentes e as duas são legítimas:

* **TWR** — "quão boas foram as escolhas". Neutraliza aporte e resgate, então é o único
  comparável com um índice, que por definição não recebe aporte.
* **XIRR** — "quanto o MEU dinheiro rendeu". Pondera pelo capital efetivamente exposto, e
  por isso é sensível a QUANDO o dinheiro entrou. Não se compara com índice.

**Convenção de ponderação dentro do período: Dietz modificado**, com peso pela fração de
DIAS CORRIDOS restantes até o fim do período:

    r_i = (V_fim − V_inicio − fluxo_liquido) / (V_inicio + Σ fluxo_j × w_j)
    w_j = (dias de d_j até o fim) / (dias do período)

Dias corridos e não dias úteis: o valor da carteira é medido em datas de calendário e a
série é semanal, então dia útil aqui só acrescentaria uma dependência de feriário sem
mudar o resultado de forma material.

**Sinal dos fluxos, e é aqui que dá errado com facilidade.** O que medimos como patrimônio
são as POSIÇÕES (Ghostfolio) mais os saldos de renda fixa marcados. Caixa parado fora
disso não é medido. Então:

* compra: entrada `+(valor + taxa)` — a taxa também saiu do seu bolso, e contá-la é o que
  faz o custo aparecer como perda em vez de sumir;
* venda: saída `−(valor − taxa)`;
* **dividendo: saída** `−valor`. Parece contraintuitivo, mas é o que credita o provento
  como RETORNO: o preço cai ex-dividendo e o dinheiro sai do que é medido, então sem
  registrar a saída o TWR leria a queda como prejuízo. Reinvestir gera uma compra logo em
  seguida, que entra como aporte — e o par se anula corretamente.

Tudo aqui é função pura sobre listas de dicts. A orquestração (Ghostfolio, banco) fica em
`services/weekly.py`.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

# Tipos de transação do Ghostfolio que movem dinheiro para dentro / para fora do que é
# medido como patrimônio.
INFLOW_TYPES = ("BUY",)
OUTFLOW_TYPES = ("SELL", "DIVIDEND")


def normalize_flows(activities: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transações do Ghostfolio -> fluxos com sinal. Ver a convenção na docstring do módulo."""
    out: List[Dict[str, Any]] = []
    for a in activities:
        tipo = (a.get("type") or "").upper()
        valor = float(a.get("value") or 0.0)
        taxa = float(a.get("fee") or 0.0)
        if tipo in INFLOW_TYPES:
            amount = valor + taxa
        elif tipo in OUTFLOW_TYPES:
            amount = -(valor - taxa)
        else:
            continue  # tipo que não move caixa (ex.: ITEM/LIABILITY) não é fluxo
        if amount == 0:
            continue
        out.append({
            "date": str(a.get("date"))[:10],
            "amount": round(amount, 2),
            "source": "rv",
            "kind": tipo,
            "ticker": a.get("ticker"),
        })
    return out


def fixed_income_flows(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Lançamentos da renda fixa -> fluxos. `balance` NÃO é fluxo: é medição de valor.

    Confundir os dois é o erro clássico aqui — um saldo atualizado de 10.000 para 10.120
    não é um aporte de 120, é o rendimento que a série quer justamente medir.
    """
    out: List[Dict[str, Any]] = []
    for e in entries:
        kind = (e.get("kind") or "").lower()
        if kind not in ("deposit", "withdrawal"):
            continue
        amount = float(e.get("amount") or 0.0)
        out.append({
            "date": str(e.get("entry_date"))[:10],
            "amount": round(amount if kind == "deposit" else -amount, 2),
            "source": "rf",
            "kind": kind,
            "account_id": e.get("account_id"),
        })
    return out


def flows_between(
    flows: Iterable[Dict[str, Any]], start: date, end: date
) -> List[Dict[str, Any]]:
    """Fluxos no intervalo (start, end] — abre exclusivo, fecha inclusivo.

    A convenção evita contar o mesmo fluxo em duas semanas seguidas: o que acontece no dia
    do fechamento pertence à semana que fecha, não à seguinte.
    """
    out = []
    for f in flows:
        try:
            d = date.fromisoformat(str(f["date"])[:10])
        except (ValueError, KeyError, TypeError):
            continue
        if start < d <= end:
            out.append({**f, "date": d.isoformat()})
    return sorted(out, key=lambda f: f["date"])


def period_return(
    start_value: float,
    end_value: float,
    flows: Sequence[Dict[str, Any]],
    start: date,
    end: date,
) -> Dict[str, Any]:
    """Retorno de UM período por Dietz modificado.

    Devolve `{'net', 'weighted', 'r'}`. `r` é `None` quando não há capital exposto — sem
    denominador não existe taxa, e devolver 0.0 diria "rendeu nada", que é outra coisa.
    """
    dias = (end - start).days
    net = 0.0
    weighted = 0.0
    for f in flows:
        amount = float(f["amount"])
        net += amount
        if dias > 0:
            d = date.fromisoformat(str(f["date"])[:10])
            peso = min(1.0, max(0.0, (end - d).days / dias))
        else:
            peso = 0.0
        weighted += amount * peso

    base = start_value + weighted
    ganho = end_value - start_value - net
    r = round(ganho / base, 8) if base > 0 else None
    return {"net": round(net, 2), "weighted": round(weighted, 2), "r": r}


def chain(returns: Iterable[Optional[float]]) -> Optional[float]:
    """Encadeia retornos de período: Π(1+r) − 1. Períodos sem taxa são pulados."""
    growth = 1.0
    visto = False
    for r in returns:
        if r is None:
            continue
        if r <= -1:  # período que zerou o capital: taxa não faz sentido
            continue
        growth *= 1.0 + r
        visto = True
    return round(growth - 1.0, 8) if visto else None


def annualize(cumulative: Optional[float], days: int) -> Optional[float]:
    """Retorno acumulado -> equivalente anual. `None` em janela curta demais.

    Abaixo de 30 dias a anualização vira ficção: 1% em uma semana viram 68% ao ano, e o
    número aparece na tela com cara de projeção.
    """
    if cumulative is None or days < 30 or cumulative <= -1:
        return None
    return round((1.0 + cumulative) ** (365.0 / days) - 1.0, 6)


# --- XIRR ---------------------------------------------------------------------------

def _npv(rate: float, cashflows: Sequence[tuple[date, float]], base: date) -> float:
    total = 0.0
    for d, amount in cashflows:
        anos = (d - base).days / 365.0
        total += amount / ((1.0 + rate) ** anos)
    return total


def xirr(
    cashflows: Sequence[tuple[date, float]], guess: float = 0.1
) -> Optional[float]:
    """Taxa interna de retorno com datas irregulares.

    Convenção do sinal: aporte é NEGATIVO (saiu do seu bolso) e o valor final é POSITIVO.
    Devolve `None` quando não há solução — o que acontece de verdade e não é erro: uma
    série sem troca de sinal (só aportes, sem valor final) não tem taxa.

    Newton-Raphson com BISSEÇÃO de reserva. Só Newton diverge em séries reais com fluxos
    grandes e próximos, e uma taxa divergida vira "+4.000% a.a." na tela sem nada avisar.
    """
    if len(cashflows) < 2:
        return None
    if not (any(a > 0 for _, a in cashflows) and any(a < 0 for _, a in cashflows)):
        return None  # sem troca de sinal não existe raiz

    base = min(d for d, _ in cashflows)
    rate = guess
    for _ in range(60):
        try:
            f = _npv(rate, cashflows, base)
            derivada = (_npv(rate + 1e-6, cashflows, base) - f) / 1e-6
        except (OverflowError, ZeroDivisionError):
            break
        if abs(f) < 1e-7:
            return round(rate, 6)
        if derivada == 0:
            break
        passo = f / derivada
        novo = rate - passo
        if novo <= -0.9999 or abs(novo) > 1e6:
            break
        rate = novo
    else:
        return round(rate, 6) if -0.9999 < rate < 1e6 else None

    # Newton não convergiu: bisseção num intervalo amplo mas finito.
    lo, hi = -0.9999, 10.0
    try:
        f_lo, f_hi = _npv(lo, cashflows, base), _npv(hi, cashflows, base)
    except (OverflowError, ZeroDivisionError):
        return None
    if f_lo * f_hi > 0:
        return None  # a raiz não está no intervalo — melhor nenhum número que um errado
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = _npv(mid, cashflows, base)
        if abs(f_mid) < 1e-9:
            break
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return round((lo + hi) / 2, 6)


def money_weighted_return(
    flows: Sequence[Dict[str, Any]], final_value: float, final_date: date,
    initial_value: float = 0.0, initial_date: Optional[date] = None,
) -> Optional[float]:
    """XIRR anualizado da carteira. `flows` no sinal deste módulo (aporte positivo).

    A conversão de sinal acontece aqui: para o XIRR, o dinheiro que ENTRA na carteira é
    saída do seu bolso e entra negativo.
    """
    cash: List[tuple[date, float]] = []
    if initial_value > 0 and initial_date is not None:
        cash.append((initial_date, -initial_value))
    for f in flows:
        try:
            d = date.fromisoformat(str(f["date"])[:10])
        except (ValueError, KeyError, TypeError):
            continue
        cash.append((d, -float(f["amount"])))
    cash.append((final_date, float(final_value)))
    return xirr(cash)


# --- semana ISO ---------------------------------------------------------------------

def week_key(d: date) -> str:
    """Chave 'yyyy-Www' da semana ISO — espelha o 'yyyy-mm' dos snapshots mensais."""
    ano, semana, _ = d.isocalendar()
    return f"{ano}-W{semana:02d}"


def week_end(d: date) -> date:
    """Domingo que FECHA a semana ISO de `d` (ISO: segunda=1 … domingo=7)."""
    return d + timedelta(days=7 - d.isoweekday())


def weeks_between(start: date, end: date) -> List[date]:
    """Domingos de fechamento entre duas datas, inclusive."""
    cur = week_end(start)
    out = []
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=7)
    return out
