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


def test_curated_sectors_are_specific():
    """A curadoria precisa devolver o setor real de cada ativo — 'Outros' aqui
    significa classificação perdida (o setor aparece no detalhe do ativo)."""
    for ticker in ("BBAS3", "TAEE11", "SBSP3", "BBSE3", "VIVT3"):
        sector = resolve_sector(ticker, "STOCK", None)
        assert sector and sector.lower() not in ("outros", "desconhecido")


# --- passo zero: override do usuário ---

async def test_override_de_bucket_vence_o_provedor(monkeypatch):
    """A atribuição manual responde outra pergunta: o StatusInvest diz o que o ativo É, e o
    bucket diz em que cesta o usuário decidiu comprá-lo. Quem dirige a compra manda."""
    from app.cache.store import Cache
    from app.services.classify import classify_ticker

    consultou = False

    async def nunca_deveria_ser_chamado(ticker, cache):
        nonlocal consultou
        consultou = True
        return "ETF"

    monkeypatch.setattr("app.services.classify.statusinvest.classify", nunca_deveria_ser_chamado)
    cls = await classify_ticker("zzzz11.sa", Cache(), "ETF", {"ZZZZ11": "RENDA_FIXA"})
    assert cls == "RENDA_FIXA"
    assert consultou is False  # o passo zero corta antes de qualquer rede


async def test_sem_override_a_cascata_antiga_continua(monkeypatch):
    from app.cache.store import Cache
    from app.services.classify import classify_ticker

    async def sem_resposta(ticker, cache):
        return None

    monkeypatch.setattr("app.services.classify.statusinvest.classify", sem_resposta)
    assert await classify_ticker("ZZZZ11", Cache(), "ETF", {"OUTRO11": "RENDA_FIXA"}) == "ETF"
    assert await classify_ticker("FOOB34", Cache(), None, None) == "BDR"
