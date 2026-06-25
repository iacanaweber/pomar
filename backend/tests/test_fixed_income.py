"""Testes da lógica pura de renda fixa (saldo, dias úteis, rendimento)."""
from __future__ import annotations

from datetime import date

from app.cache.store import Cache
from app.clients.sgs_bcb import SgsClient
from app.services import fixed_income as fi


def test_business_days_excludes_weekend_and_holiday():
    # 02/06/2025 (seg) -> 09/06/2025 (seg): ter,qua,qui,sex,seg = 5 dias úteis (sem feriado)
    assert fi.business_days_between(date(2025, 6, 2), date(2025, 6, 9)) == 5
    # sex -> seg = só a seg
    assert fi.business_days_between(date(2025, 6, 6), date(2025, 6, 9)) == 1
    # intervalo vazio/invertido
    assert fi.business_days_between(date(2025, 6, 9), date(2025, 6, 9)) == 0
    # feriado no meio: 01/05/2025 (qui, Dia do Trabalho) não conta
    assert fi.business_days_between(date(2025, 4, 30), date(2025, 5, 2)) == 1  # só 02/05 (sex)


def test_annualized_return_basic():
    res = fi.annualized_return(10_000.0, 10_105.0, 21)  # +1,05% em ~1 mês de pregão
    assert res is not None
    assert abs(res["gain"] - 105.0) < 1e-6
    # (1.0105)^(252/21) - 1 ≈ 0.1335
    assert abs(res["annualized"] - 0.1335) < 0.005


def test_annualized_return_guards():
    assert fi.annualized_return(0.0, 100.0, 21) is None       # sem principal
    assert fi.annualized_return(1000.0, 1100.0, 0) is None     # sem dias úteis


def test_current_balance_with_deposits_after_last_balance():
    entries = [
        {"id": 1, "kind": "balance", "amount": 10_000.0, "entry_date": "2025-02-03"},
        {"id": 2, "kind": "deposit", "amount": 200.0, "entry_date": "2025-02-10"},
        {"id": 3, "kind": "withdrawal", "amount": 100.0, "entry_date": "2025-02-12"},
    ]
    assert fi.current_balance(entries) == 10_100.0


def test_last_yield_treats_midperiod_deposit_as_principal():
    entries = [
        {"id": 1, "kind": "balance", "amount": 10_000.0, "entry_date": "2025-01-02"},
        {"id": 2, "kind": "deposit", "amount": 500.0, "entry_date": "2025-01-15"},
        {"id": 3, "kind": "balance", "amount": 11_000.0, "entry_date": "2025-02-03"},
    ]
    ly = fi.last_yield(entries)
    assert ly is not None
    assert ly["principal_before"] == 10_500.0  # aporte entra como principal, não como rendimento
    assert ly["gain"] == 500.0                  # 11000 - 10500
    assert ly["annualized"] is not None and ly["annualized"] > 0


def test_last_yield_needs_a_baseline():
    # um único saldo SEM nenhum aporte anterior não tem base para calcular
    entries = [{"id": 1, "kind": "balance", "amount": 10_000.0, "entry_date": "2025-01-02"}]
    assert fi.last_yield(entries) is None


def test_last_yield_from_deposit_baseline():
    # 1 aporte + 1 atualização de saldo (datas diferentes) DEVE calcular
    entries = [
        {"id": 1, "kind": "deposit", "amount": 10_000.0, "entry_date": "2026-06-01"},
        {"id": 2, "kind": "balance", "amount": 10_128.41, "entry_date": "2026-06-25"},
    ]
    ly = fi.last_yield(entries)
    assert ly is not None
    assert ly["principal_before"] == 10_000.0
    assert abs(ly["gain"] - 128.41) < 1e-6
    assert ly["annualized"] is not None and ly["annualized"] > 0


def test_last_yield_deposit_same_day_as_balance_is_none():
    # aporte e saldo no mesmo dia => 0 dias úteis => sem taxa
    entries = [
        {"id": 1, "kind": "deposit", "amount": 10_000.0, "entry_date": "2026-06-25"},
        {"id": 2, "kind": "balance", "amount": 10_005.0, "entry_date": "2026-06-25"},
    ]
    assert fi.last_yield(entries) is None


def test_pct_of_cdi():
    assert fi.pct_of_cdi(0.14, 0.14) == 1.0
    assert fi.pct_of_cdi(0.07, 0.14) == 0.5
    assert fi.pct_of_cdi(None, 0.14) is None
    assert fi.pct_of_cdi(0.14, None) is None


async def test_sgs_cdi_annual_from_cache():
    """Anualização do CDI diário sem rede (valor pré-populado no cache)."""
    cache = Cache()
    cache.set("sgs:12", 0.052531, 3600)  # CDI %/dia (valor real verificado ~14,15% a.a.)
    sgs = SgsClient(cache)
    cdi = await sgs.cdi_annual()
    assert cdi is not None and abs(cdi - 0.1415) < 0.002
