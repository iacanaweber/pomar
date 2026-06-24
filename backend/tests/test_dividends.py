"""Testes do provedor StatusInvest: tipo de provento, datas e DY trailing-365d."""
from __future__ import annotations

from datetime import date

from app.providers import statusinvest as si


def test_net_factor_by_type():
    assert si._net_factor("JCP") == 0.85
    assert si._net_factor("Juros Sobre Capital Próprio") == 0.85
    assert si._net_factor("Rend. Tributado") == 0.85
    assert si._net_factor("Dividendo") == 1.0
    assert si._net_factor("Rendimento") == 1.0  # FII isento p/ PF
    assert si._net_factor(None) == 1.0


def test_parse_date():
    assert si._parse_date("04/01/2027") == date(2027, 1, 4)
    assert si._parse_date("lixo") is None
    assert si._parse_date(None) is None


def test_trailing_365_gross_and_net():
    today = date(2026, 6, 24)
    payments = [
        {"pd": "01/06/2026", "v": 1.0, "et": "Dividendo"},  # dentro de 365d, isento
        {"pd": "01/06/2026", "v": 1.0, "et": "JCP"},         # dentro, JCP (×0,85)
        {"pd": "01/01/2024", "v": 5.0, "et": "Dividendo"},   # > 365d atrás: fora
        {"pd": "04/01/2027", "v": 9.0, "et": "JCP"},         # futuro: ignora
    ]
    assert si._trailing_365(payments, today, net=False) == 2.0
    assert abs(si._trailing_365(payments, today, net=True) - 1.85) < 1e-9  # 1.0 + 0.85
