"""Renda fixa — lógica pura (testável) de saldo e rendimento.

O usuário mantém uma lista de contas de RF (CDB, Tesouro, conta remunerada…). Em cada conta
lança eventos: 'balance' (atualização de saldo observado), 'deposit' (aporte) e 'withdrawal'
(resgate). O histórico vira uma sequência de SUB-PERÍODOS entre saldos observados; cada um
rende à sua própria taxa, calculada por Modified Dietz (aportes e resgates pesam pela fração
do período em que o dinheiro ficou aplicado) e anualizada em base 252 dias úteis.

O número que a tela mostra é o de `history_yield`: o encadeamento de TODOS os sub-períodos.
Olhar só a última janela dava uma taxa refém de quando o usuário atualiza o saldo — numa
janela de 2 dias úteis, R$1 de imprecisão vira 1,2 p.p. na taxa anual.

Tudo aqui é função pura sobre listas de dicts — sem I/O. A orquestração (DB, CDI) fica na rota.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from app.data.holidays_b3 import B3_HOLIDAYS

_DAY = timedelta(days=1)


def parse_date(value: str) -> date:
    """Aceita ISO 'yyyy-mm-dd' (com ou sem hora). Lança ValueError se inválido."""
    s = str(value).strip()
    return datetime.fromisoformat(s).date() if "T" in s or " " in s else date.fromisoformat(s)


def business_days_between(d1: date, d2: date, holidays: frozenset[date] = B3_HOLIDAYS) -> int:
    """Dias úteis no intervalo (d1, d2] — seg–sex, excluindo feriados da B3.

    Convenção: exclui o dia inicial e inclui o final (nº de "passos" de pregão entre as datas).
    Retorna 0 se d2 <= d1.
    """
    if d2 <= d1:
        return 0
    count = 0
    cur = d1 + _DAY
    while cur <= d2:
        if cur.weekday() < 5 and cur not in holidays:
            count += 1
        cur += _DAY
    return count


def annualized_from(gain: float, base: float, business_days: int) -> Optional[Dict]:
    """Anualiza (base 252) um ganho sobre uma base de capital — núcleo do Modified Dietz.

    `base` é o capital MÉDIO ponderado pelo tempo (não o principal nominal). Retorna None
    quando não dá para inferir taxa (base <= 0 ou sem dias úteis).
    """
    if base <= 0 or business_days <= 0:
        return None
    period_return = gain / base
    if period_return <= -1:  # zerou/negativou além do principal: taxa não faz sentido
        return {"gain": round(gain, 2), "period_return": round(period_return, 6),
                "annualized": None, "business_days": business_days}
    daily = (1.0 + period_return) ** (1.0 / business_days) - 1.0
    annualized = (1.0 + daily) ** 252 - 1.0
    return {
        "gain": round(gain, 2),
        "period_return": round(period_return, 6),
        "annualized": round(annualized, 6),
        "business_days": business_days,
    }


def annualized_return(principal_before: float, new_balance: float, business_days: int) -> Optional[Dict]:
    """Rendimento simples (sem fluxos no meio), anualizado em base 252 dias úteis."""
    if principal_before <= 0:
        return None
    return annualized_from(new_balance - principal_before, principal_before, business_days)


_FLOW_KINDS = ("deposit", "withdrawal")


def _sorted(entries: List[Dict]) -> List[Dict]:
    """Ordem canônica dos lançamentos: por data e, no mesmo dia, pela ordem em que foram
    lançados (id crescente). Essa desempate é o que diz se um resgate aconteceu antes ou
    depois do saldo informado no mesmo dia."""
    return sorted(entries, key=lambda e: (str(e["entry_date"]), int(e.get("id", 0))))


def _signed(entry: Dict) -> float:
    """Fluxo com sinal: aporte entra positivo, resgate negativo."""
    amount = float(entry["amount"])
    return amount if entry["kind"] == "deposit" else -amount


def _flows_in(entries: List[Dict]) -> List[tuple[date, float]]:
    return [(parse_date(e["entry_date"]), _signed(e)) for e in entries if e["kind"] in _FLOW_KINDS]


def current_balance(entries: List[Dict]) -> float:
    """Saldo atual = último 'balance' + (aportes − resgates) lançados DEPOIS dele.

    "Depois" é posição na ordem canônica, não data: quem atualiza o saldo de manhã e resgata
    à tarde lança os dois no mesmo dia, e comparar só datas descartava o resgate — o saldo
    ficava superestimado em silêncio.
    """
    ev = _sorted(entries)
    idx = [i for i, e in enumerate(ev) if e["kind"] == "balance"]
    last = idx[-1] if idx else None
    bal = float(ev[last]["amount"]) if last is not None else 0.0
    tail = ev[last + 1:] if last is not None else ev
    return round(bal + sum(a for _, a in _flows_in(tail)), 2)


def _segments(entries: List[Dict]) -> List[Dict]:
    """Quebra o histórico em sub-períodos entre saldos observados.

    A fronteira de cada sub-período é POSICIONAL (índice na lista ordenada), não a data:
    um aporte lançado no mesmo dia de um saldo, porém depois dele, pertence ao sub-período
    seguinte. Comparar só datas fazia esse aporte sumir da conta — o saldo final já o
    continha, e ele reaparecia como "rendimento" (R$5.000 aportados viravam 10.000% a.a.).

    O primeiro sub-período abre no saldo mais antigo; havendo aportes ANTES dele, abre no
    primeiro aporte, com capital inicial zero.
    """
    ev = _sorted(entries)
    idx = [i for i, e in enumerate(ev) if e["kind"] == "balance"]
    if not idx:
        return []
    out: List[Dict] = []
    first = idx[0]
    pre = _flows_in(ev[:first])
    if pre:
        out.append({
            "start_capital": 0.0,
            "d1": min(d for d, _ in pre),
            "end_amount": float(ev[first]["amount"]),
            "d2": parse_date(ev[first]["entry_date"]),
            "flows": pre,
        })
    for a, b in zip(idx, idx[1:]):
        out.append({
            "start_capital": float(ev[a]["amount"]),
            "d1": parse_date(ev[a]["entry_date"]),
            "end_amount": float(ev[b]["amount"]),
            "d2": parse_date(ev[b]["entry_date"]),
            "flows": _flows_in(ev[a + 1:b]),
        })
    return out


def _dietz(seg: Dict, holidays: frozenset[date]) -> Optional[tuple[float, float, int]]:
    """(ganho, capital médio, dias úteis) de um sub-período — núcleo do Modified Dietz.

    Cada fluxo pesa pela fração do período que passou aplicado: na abertura pesa 1, na data
    do saldo final pesa 0. Peso limitado a [0, 1] porque um lançamento retroagido pode cair
    antes da abertura do sub-período. None quando não dá para inferir taxa.
    """
    bd = business_days_between(seg["d1"], seg["d2"], holidays)
    if bd <= 0:
        return None
    base = seg["start_capital"] + sum(
        a * min(1.0, max(0.0, business_days_between(d, seg["d2"], holidays) / bd))
        for d, a in seg["flows"]
    )
    if base <= 0:
        return None
    gain = seg["end_amount"] - seg["start_capital"] - sum(a for _, a in seg["flows"])
    return gain, base, bd


def last_yield(entries: List[Dict], holidays: frozenset[date] = B3_HOLIDAYS) -> Optional[Dict]:
    """Rendimento da ÚLTIMA atualização de saldo vs o saldo anterior.

    Só diagnóstico: a janela é curta e o usuário escolhe seu tamanho ao decidir quando
    atualizar o saldo, então a taxa anualizada daqui oscila muito. O número que vale para
    comparar com o CDI é o de `history_yield`.
    """
    segs = _segments(entries)
    if not segs:
        return None
    seg = segs[-1]
    dietz = _dietz(seg, holidays)
    if dietz is None:
        return None
    gain, base, bd = dietz
    res = annualized_from(gain, base, bd)
    if res is None:
        return None
    res.update({
        "from_date": seg["d1"].isoformat(),
        "to_date": seg["d2"].isoformat(),
        "principal_after_flows": round(seg["start_capital"] + sum(a for _, a in seg["flows"]), 2),
    })
    return res


def history_yield(entries: List[Dict], holidays: frozenset[date] = B3_HOLIDAYS) -> Optional[Dict]:
    """Rendimento de TODO o histórico — retorno tempo-ponderado (TWR), base 252.

    Cada sub-período rende à sua taxa; o retorno do histórico é o produto
    (1+r₁)(1+r₂)…(1+rₙ) − 1. Encadear é o que torna a taxa comparável ao CDI: quando o
    usuário aporta ou resgata deixa de mover o número (ao contrário do retorno ponderado
    por dinheiro), e o ruído de uma janela curta se dilui no histórico inteiro em vez de
    virar a manchete.

    `gain` é o dinheiro de fato ganho no período (saldo final − capital inicial − fluxos
    líquidos) — esse sim ponderado por dinheiro, porque é caixa, não taxa.
    """
    segs = _segments(entries)
    if not segs:
        return None

    growth = 1.0
    total_bd = 0
    for seg in segs:
        dietz = _dietz(seg, holidays)
        if dietz is None:
            continue
        gain, base, bd = dietz
        period_return = gain / base
        if period_return <= -1:  # sub-período que zerou o capital: taxa não faz sentido
            continue
        growth *= 1.0 + period_return
        total_bd += bd
    if total_bd <= 0:
        return None

    net_flows = sum(a for seg in segs for _, a in seg["flows"])
    gain = segs[-1]["end_amount"] - segs[0]["start_capital"] - net_flows
    return {
        "gain": round(gain, 2),
        "period_return": round(growth - 1.0, 6),
        "annualized": round(growth ** (252.0 / total_bd) - 1.0, 6),
        "business_days": total_bd,
        "from_date": segs[0]["d1"].isoformat(),
        "to_date": segs[-1]["d2"].isoformat(),
    }


def pct_of_cdi(annualized: Optional[float], cdi_annual: Optional[float]) -> Optional[float]:
    """Rendimento como fração do CDI (ex.: 1.02 = 102% do CDI). None se faltar dado.

    Taxa negativa não vira "% do CDI": "−18% do CDI" se lê como um rendimento, mas a conta
    encolheu. Quem chama mostra a taxa negativa e omite a comparação.
    """
    if annualized is None or annualized < 0 or not cdi_annual or cdi_annual <= 0:
        return None
    return round(annualized / cdi_annual, 4)
