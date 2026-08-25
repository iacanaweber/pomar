"""Cliente do SGS: acumulação do IPCA e o que acontece quando o Banco Central não responde."""
from __future__ import annotations

from datetime import date

import pytest

from app.cache.store import Cache
from app.clients.sgs_bcb import SgsClient


def _client() -> SgsClient:
    return SgsClient(Cache())


async def test_ipca_ignora_o_mes_da_data_base(monkeypatch):
    """O IPCA de um mês mede o mês inteiro. Incluir o mês da data-base corrigiria por um
    período que ainda não tinha começado — errar para menos é o lado certo num piso."""

    async def serie(self, code, start, end=None):
        return [
            {"date": date(2026, 1, 1), "value": 0.5},   # mês da data-base: fora
            {"date": date(2026, 2, 1), "value": 1.0},
            {"date": date(2026, 3, 1), "value": 2.0},
        ]

    monkeypatch.setattr(SgsClient, "series_range", serie)
    fator = await _client().ipca_factor_since(date(2026, 1, 15))
    assert fator == pytest.approx(1.01 * 1.02)


async def test_ipca_acumula_multiplicando_e_nao_somando(monkeypatch):
    async def serie(self, code, start, end=None):
        return [{"date": date(2026, m, 1), "value": 1.0} for m in (2, 3, 4)]

    monkeypatch.setattr(SgsClient, "series_range", serie)
    fator = await _client().ipca_factor_since(date(2026, 1, 1))
    assert fator == pytest.approx(1.01**3)      # 3,0301%, não 3%
    assert fator != pytest.approx(1.03)


async def test_sem_serie_o_fator_e_none(monkeypatch):
    """`None` deixa quem chama decidir: falha de índice nunca derruba a tela."""

    async def sem_dados(self, code, start, end=None):
        return None

    monkeypatch.setattr(SgsClient, "series_range", sem_dados)
    assert await _client().ipca_factor_since(date(2026, 1, 1)) is None


async def test_janela_invertida_nao_chama_a_rede():
    assert await _client().series_range(433, date(2026, 5, 1), date(2026, 1, 1)) == []


async def test_intervalo_sem_observacao_e_serie_vazia_nao_indisponibilidade(monkeypatch):
    """O SGS responde 404 "Value(s) not found" quando o intervalo não tem observação.

    Acontece no caso mais comum de todos: piso da reserva definido neste mês, cujo IPCA só
    fecha no mês que vem. Tratar isso como falha fazia a tela anunciar "IPCA indisponível",
    sugerindo Banco Central fora do ar — quando a resposta correta é "não há correção
    ainda", e o fator é 1,0.
    """

    class Resp:
        status_code = 404

        def raise_for_status(self):
            raise AssertionError("404 de intervalo vazio não deve chegar ao raise_for_status")

        def json(self):
            raise AssertionError("não há corpo útil a ler num 404")

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            return Resp()

    monkeypatch.setattr("app.clients.sgs_bcb.httpx.AsyncClient", lambda **kw: FakeAsyncClient())

    c = _client()
    assert await c.series_range(433, date(2026, 8, 24)) == []
    # e o fator resultante é 1,0 — sem correção, não "indisponível"
    assert await c.ipca_factor_since(date(2026, 8, 24)) == 1.0
