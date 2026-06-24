"""Testes do pré-corte de reserva/renda fixa no aporte."""
from __future__ import annotations

from app.services import reserve as r


def test_no_target_sends_all_to_rv():
    out = r.split_aporte_reserva(1000.0, total_rv=10_000.0, reserve_current=0.0, reserve_target=0.0)
    assert out["reserve_directed"] == 0.0
    assert out["aporte_rv"] == 1000.0


def test_reserve_already_full_directs_nothing():
    # alvo 30% de (10000+5000+1000)=16000 -> 4800; já tem 5000 -> need negativo
    out = r.split_aporte_reserva(1000.0, total_rv=10_000.0, reserve_current=5000.0, reserve_target=0.3)
    assert out["reserve_directed"] == 0.0
    assert out["aporte_rv"] == 1000.0


def test_reserve_empty_consumes_whole_aporte():
    out = r.split_aporte_reserva(1000.0, total_rv=10_000.0, reserve_current=0.0, reserve_target=0.3)
    assert out["reserve_directed"] == 1000.0
    assert out["aporte_rv"] == 0.0


def test_reserve_partial_split():
    # need = 0.3*(10000+2000+5000) - 2000 = 0.3*17000 - 2000 = 3100
    out = r.split_aporte_reserva(5000.0, total_rv=10_000.0, reserve_current=2000.0, reserve_target=0.3)
    assert out["reserve_directed"] == 3100.0
    assert out["aporte_rv"] == 1900.0


def test_reserve_status_fields():
    s = r.reserve_status(total_rv=10_000.0, reserve_current=2000.0, reserve_target=0.3, aporte=5000.0)
    assert s["target_amount"] == 5100.0  # 0.3 * 17000
    assert s["gap"] == 3100.0
    assert 0.0 <= s["pct_filled"] <= 1.0
