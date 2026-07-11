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


def test_dietz_resgate_no_meio_nao_infla_taxa():
    """Cenário da auditoria: 10k aportados em jan, 5k resgatados em nov, saldo 5.600 em
    dez. O método antigo dava ~13,9% a.a. (dividia o ganho por 5.000, como se os 10k
    nunca tivessem rendido); o Modified Dietz pondera o resgate pelo tempo."""
    entries = [
        {"id": 1, "kind": "deposit", "amount": 10_000.0, "entry_date": "2026-01-02"},
        {"id": 2, "kind": "withdrawal", "amount": 5_000.0, "entry_date": "2026-11-03"},
        {"id": 3, "kind": "balance", "amount": 5_600.0, "entry_date": "2026-12-01"},
    ]
    res = fi.last_yield(entries)
    assert res is not None and res["annualized"] is not None
    assert res["gain"] == 600.0
    assert res["annualized"] < 0.10  # antigo: ~0.139
    assert res["annualized"] > 0.04


def test_dietz_um_aporte_um_saldo_continua_exato():
    """O caso simples (1 aporte + 1 saldo) não muda com o Dietz: peso do aporte = 1."""
    entries = [
        {"id": 1, "kind": "deposit", "amount": 10_000.0, "entry_date": "2026-01-02"},
        {"id": 2, "kind": "balance", "amount": 10_100.0, "entry_date": "2026-02-02"},
    ]
    res = fi.last_yield(entries)
    assert res is not None
    assert abs(res["period_return"] - 0.01) < 1e-9


def test_feriados_gerados_batem_com_a_lista_curada_2024_2027():
    """Golden test: o gerador algorítmico reproduz exatamente a antiga lista curada
    (2024–2027) — e segue funcionando em 2028+ sem manutenção anual."""
    from datetime import date

    from app.data.holidays_b3 import B3_HOLIDAYS, b3_holidays_for_year

    curado = {
        2024: {(1, 1), (2, 12), (2, 13), (3, 29), (4, 21), (5, 1), (5, 30), (9, 7),
               (10, 12), (11, 2), (11, 15), (11, 20), (12, 24), (12, 25), (12, 31)},
        2025: {(1, 1), (3, 3), (3, 4), (4, 18), (4, 21), (5, 1), (6, 19), (9, 7),
               (10, 12), (11, 2), (11, 15), (11, 20), (12, 24), (12, 25), (12, 31)},
        2026: {(1, 1), (2, 16), (2, 17), (4, 3), (4, 21), (5, 1), (6, 4), (9, 7),
               (10, 12), (11, 2), (11, 15), (11, 20), (12, 24), (12, 25), (12, 31)},
        2027: {(1, 1), (2, 8), (2, 9), (3, 26), (4, 21), (5, 1), (5, 27), (9, 7),
               (10, 12), (11, 2), (11, 15), (11, 20), (12, 24), (12, 25), (12, 31)},
    }
    for year, mmdd in curado.items():
        gerado = {(d.month, d.day) for d in b3_holidays_for_year(year)}
        assert gerado == mmdd, f"divergência em {year}"
    # 2028+ coberto (era o ponto cego): Sexta-feira Santa de 2028 = 14/04
    assert date(2028, 4, 14) in B3_HOLIDAYS
    assert date(2030, 1, 1) in B3_HOLIDAYS
