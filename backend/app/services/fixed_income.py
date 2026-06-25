"""Renda fixa — lógica pura (testável) de saldo e rendimento.

O usuário mantém uma lista de contas de RF (CDB, Tesouro, conta remunerada…). Em cada conta
lança eventos: 'balance' (atualização de saldo observado), 'deposit' (aporte) e 'withdrawal'
(resgate). O RENDIMENTO é derivado de uma atualização de saldo: comparamos o saldo novo com o
principal esperado (saldo anterior + aportes − resgates do período) e anualizamos pela contagem
de DIAS ÚEIS (base 252) entre as duas atualizações de saldo.

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


def annualized_return(principal_before: float, new_balance: float, business_days: int) -> Optional[Dict]:
    """Rendimento de uma atualização de saldo, anualizado em base 252 dias úteis.

    Retorna None quando não dá para inferir taxa (sem principal anterior, sem dias úteis ou
    principal <= 0). O ganho em R$ ainda pode ser exibido pelo chamador nesses casos.
    """
    if principal_before <= 0 or business_days <= 0:
        return None
    gain = new_balance - principal_before
    period_return = gain / principal_before
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


def _sorted(entries: List[Dict]) -> List[Dict]:
    return sorted(entries, key=lambda e: (str(e["entry_date"]), int(e.get("id", 0))))


def current_balance(entries: List[Dict]) -> float:
    """Saldo atual = último 'balance' + (aportes − resgates) lançados APÓS aquela data."""
    ev = _sorted(entries)
    last_balance_val = 0.0
    last_balance_date: Optional[date] = None
    for e in ev:
        if e["kind"] == "balance":
            last_balance_val = float(e["amount"])
            last_balance_date = parse_date(e["entry_date"])
    bal = last_balance_val
    for e in ev:
        if e["kind"] in ("deposit", "withdrawal"):
            d = parse_date(e["entry_date"])
            if last_balance_date is None or d > last_balance_date:
                bal += float(e["amount"]) if e["kind"] == "deposit" else -float(e["amount"])
    return round(bal, 2)


def last_yield(entries: List[Dict], holidays: frozenset[date] = B3_HOLIDAYS) -> Optional[Dict]:
    """Rendimento da ÚLTIMA atualização de saldo vs o ponto de partida anterior.

    O ponto de partida é, em ordem de preferência:
    1. o SALDO anterior (+ aportes − resgates no período) — mais preciso; ou
    2. quando não há saldo anterior, os APORTES (líq. de resgates) até a data do saldo, com a
       data do primeiro aporte como início — exato p/ "1 aporte + 1 saldo"; conservador p/ vários.

    Retorna o dict de `annualized_return` com as datas, ou None se não há base/dias úteis.
    """
    ev = _sorted(entries)
    balances = [e for e in ev if e["kind"] == "balance"]
    if not balances:
        return None
    last = balances[-1]
    d2 = parse_date(last["entry_date"])
    if d2 is None:
        return None

    if len(balances) >= 2:
        prev = balances[-2]
        d1 = parse_date(prev["entry_date"])
        if d1 is None:
            return None
        principal = float(prev["amount"])
        for e in ev:
            if e["kind"] in ("deposit", "withdrawal"):
                d = parse_date(e["entry_date"])
                if d is not None and d1 < d <= d2:
                    principal += float(e["amount"]) if e["kind"] == "deposit" else -float(e["amount"])
    else:
        flows = []
        for e in ev:
            if e["kind"] in ("deposit", "withdrawal"):
                d = parse_date(e["entry_date"])
                if d is not None and d <= d2:
                    flows.append((d, e["kind"], float(e["amount"])))
        if not flows:
            return None
        principal = sum(a if k == "deposit" else -a for (_, k, a) in flows)
        d1 = min(d for (d, _, _) in flows)

    bd = business_days_between(d1, d2, holidays)
    res = annualized_return(principal, float(last["amount"]), bd)
    if res is None:
        return None
    res.update({"from_date": d1.isoformat(), "to_date": d2.isoformat(),
                "principal_before": round(principal, 2)})
    return res


def pct_of_cdi(annualized: Optional[float], cdi_annual: Optional[float]) -> Optional[float]:
    """Rendimento como fração do CDI (ex.: 1.02 = 102% do CDI). None se faltar dado."""
    if annualized is None or not cdi_annual or cdi_annual <= 0:
        return None
    return round(annualized / cdi_annual, 4)
