"""Testes do universo de candidatos: com carteira alvo, só o que pode ser comprado."""
from __future__ import annotations

import pytest

from app.repositories.db import Database
from app.models.market import Asset
from app.models.portfolio import Allocations, Portfolio, Position
from app.services import universe as universe_svc


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "universe.db"))
    await database.ensure_ready()
    yield database
    await database.close()


@pytest.fixture
def captured(monkeypatch):
    """Captura os tickers (e dicas de classe) pedidos ao agregador de mercado."""
    seen: dict = {}

    async def fake_build_assets(tickers, cache, brapi, class_hints=None):
        seen["tickers"] = list(tickers)
        seen["hints"] = dict(class_hints or {})
        return [
            Asset(ticker=t, asset_class=(class_hints or {}).get(t, "STOCK"), price=10.0)
            for t in tickers
        ]

    monkeypatch.setattr("app.services.market_data.build_assets", fake_build_assets)
    return seen


def _pf() -> Portfolio:
    return Portfolio(
        total_value=1000.0,
        as_of="2026-07-10T00:00:00Z",
        positions=[
            Position(ticker="ANTIGO3", asset_class="STOCK", value=600.0, weight=0.6, sector="Bancos"),
            Position(ticker="AAA3", asset_class="STOCK", value=400.0, weight=0.4),
        ],
        allocations=Allocations(by_class={"STOCK": 1.0}),
    )


async def test_baskets_fetch_only_target_portfolio_tickers(captured):
    """Com cesta, buscar posições que estão FORA da carteira alvo é gasto puro: o fetch de
    mercado domina o tempo do plano e esses ativos não podem receber compra."""
    assets = await universe_svc.build_universe(
        _pf(), None, None, class_baskets={"STOCK": {"AAA3": 0.6, "BBB3": 0.4}},
    )
    assert set(captured["tickers"]) == {"AAA3", "BBB3"}
    assert "ANTIGO3" not in captured["tickers"]
    assert captured["hints"] == {"AAA3": "STOCK", "BBB3": "STOCK"}
    assert {a.ticker for a in assets} == {"AAA3", "BBB3"}


async def test_basket_ticker_hint_wins_over_ghostfolio(captured):
    """A classe da cesta é a escolha explícita do usuário e prevalece sobre o palpite
    do Ghostfolio (que às vezes chama FII de ação)."""
    pf = Portfolio(
        total_value=100.0, as_of="2026-07-10T00:00:00Z",
        positions=[Position(ticker="XYZ11", asset_class="STOCK", value=100.0, weight=1.0)],
        allocations=Allocations(by_class={"STOCK": 1.0}),
    )
    await universe_svc.build_universe(pf, None, None, class_baskets={"FII": {"XYZ11": 1.0}})
    assert captured["hints"]["XYZ11"] == "FII"


async def test_without_baskets_uses_positions_and_watchlist(captured, db, monkeypatch):
    """Sem cesta (GET /universe, inspeção) o comportamento antigo continua: posições ∪ watchlist."""
    monkeypatch.setattr(universe_svc, "get_db", lambda: db)
    assets = await universe_svc.build_universe(_pf(), None, None)
    assert "ANTIGO3" in captured["tickers"]  # posição atual entra
    assert len(captured["tickers"]) > 2      # watchlist curada também
    assert len(assets) == len(captured["tickers"])


async def test_sector_from_ghostfolio_fills_the_gap(captured):
    """Setor que o provedor não trouxe é completado pelo Ghostfolio (não fica 'sem setor')."""
    assets = await universe_svc.build_universe(
        _pf(), None, None, class_baskets={"STOCK": {"ANTIGO3": 1.0}},
    )
    assert assets[0].sector == "Bancos"
