"""Testes da resolução de setor (mapa curado -> provedor -> default por classe)."""
from __future__ import annotations

from app.services.classify import resolve_sector


def test_curated_sector_wins_over_provider():
    # ETFs do pedido do usuário (antes "Sem setor")
    assert resolve_sector("WRLD11", "ETF", None) == "Diversificado"
    assert resolve_sector("AUVP11", "ETF", None) == "Diversificado"
    assert resolve_sector("AAPL34", "BDR", None) == "Exterior"
    # mapa curado é determinístico: vence a grafia do provedor
    assert resolve_sector("BBAS3", "STOCK", "Intermediários Financeiros") == "Bancos"
    assert resolve_sector("SAPR11", "STOCK", "Utilidade Pública") == "Saneamento"


def test_provider_then_default_by_class():
    # ticker não curado usa o setor do provedor
    assert resolve_sector("XPTO3", "STOCK", "Varejo") == "Varejo"
    # sem curado nem provedor: default por classe (nunca "Sem setor")
    assert resolve_sector("XPTO11", "ETF", None) == "Diversificado"
    assert resolve_sector("FOOB34", "BDR", "") == "Exterior"
    assert resolve_sector("ZZZZ11", "FII", None) == "Imobiliário"
    assert resolve_sector("ZZZZ3", "STOCK", None) == "Outros"


def test_resolve_sector_normalizes_ticker():
    assert resolve_sector("wrld11.sa", "ETF", None) == "Diversificado"


def test_curated_sectors_match_besst_keywords():
    # os rótulos BESST curados devem casar com BESST_KEYWORDS (afinidade determinística)
    from app.config import BESST_KEYWORDS

    for ticker in ("BBAS3", "TAEE11", "SBSP3", "BBSE3", "VIVT3"):
        sector = resolve_sector(ticker, "STOCK", None).lower()
        assert any(kw in sector for kw in BESST_KEYWORDS), f"{ticker}={sector} não casa BESST"
