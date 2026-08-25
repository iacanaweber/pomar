"""O parser de holdings do Ghostfolio, contra os dois formatos que ele já teve.

Contexto: entre os planos 42 (12/08/2026) e 43 (17/08/2026) a carteira inteira passou a
chegar com ticker "?" sem nenhum commit no meio — o Ghostfolio foi atualizado e moveu
`symbol`, `name`, `assetSubClass` e `sectors` para dentro de `assetProfile`. O parser lia
os quatro no topo e o default `"?"` engoliu a falha: as 13 posições viraram a mesma chave,
`classify_ticker("?")` caiu em STOCK, e o plano passou a comprar como se a carteira
estivesse 100% fora do alvo.

Estes testes travam os dois formatos e, principalmente, travam o que acontece quando
aparecer um TERCEIRO: falhar alto, nunca inventar posição.
"""
import pytest

from app.clients.ghostfolio import GhostfolioClient


# Recortado de uma resposta real do Ghostfolio 3.53.0 (só os campos que o parser lê).
HOLDING_ANINHADA = {
    "valueInBaseCurrency": 1488.0,
    "quantity": 80,
    "investment": 1573.83,
    "netPerformancePercent": -0.0647,
    "assetProfile": {
        "symbol": "BBAS3.SA",
        "name": "Banco do Brasil S.A.",
        "assetClass": "EQUITY",
        "assetSubClass": "STOCK",
        "sectors": [{"name": "Financial Services", "weight": 1}],
        "currency": "BRL",
    },
}

# Formato antigo: tudo no topo da holding.
HOLDING_LEGADA = {
    "symbol": "MXRF11.SA",
    "name": "Maxi Renda FII",
    "assetSubClass": "REALESTATE",
    "sectors": [{"name": "Imobiliário", "weight": 1}],
    "valueInBaseCurrency": 500.0,
    "quantity": 50,
}


async def _parse(monkeypatch, holdings: list[dict]):
    client = GhostfolioClient("http://ghostfolio.test", "token")

    async def fake_get(self, http_client, path):
        return {"holdings": holdings, "currency": "BRL"}

    monkeypatch.setattr(GhostfolioClient, "_get", fake_get)
    return await client.get_portfolio()


@pytest.mark.asyncio
async def test_le_o_formato_aninhado_atual(monkeypatch):
    """O formato de hoje: os quatro campos vêm de `assetProfile`."""
    pf = await _parse(monkeypatch, [HOLDING_ANINHADA])

    assert len(pf.positions) == 1
    p = pf.positions[0]
    assert p.ticker == "BBAS3"  # normalize_ticker tira o sufixo .SA
    assert p.name == "Banco do Brasil S.A."
    assert p.asset_class == "STOCK"
    assert p.sector == "Financial Services"


@pytest.mark.asyncio
async def test_le_o_formato_antigo_com_campos_no_topo(monkeypatch):
    """Versões anteriores traziam tudo no topo — o fallback tem que continuar valendo."""
    pf = await _parse(monkeypatch, [HOLDING_LEGADA])

    p = pf.positions[0]
    assert p.ticker == "MXRF11"
    assert p.name == "Maxi Renda FII"
    assert p.asset_class == "FII"
    assert p.sector == "Imobiliário"


@pytest.mark.asyncio
async def test_classes_nao_colapsam_todas_em_stock(monkeypatch):
    """A regressão real: sem ler `assetSubClass` aninhado, tudo caía no default STOCK
    e a alocação atual virava {"STOCK": 1.0}."""
    pf = await _parse(monkeypatch, [HOLDING_ANINHADA, HOLDING_LEGADA])

    assert set(pf.allocations.by_class) == {"STOCK", "FII"}
    assert pf.allocations.by_class["STOCK"] == pytest.approx(1488 / 1988, rel=1e-6)


@pytest.mark.asyncio
async def test_holding_sem_simbolo_nao_vira_ticker_interrogacao(monkeypatch):
    """Uma holding quebrada é PULADA. Antes ela entrava como "?" e contaminava o plano."""
    quebrada = {"valueInBaseCurrency": 100.0, "quantity": 1}
    pf = await _parse(monkeypatch, [HOLDING_ANINHADA, quebrada])

    assert [p.ticker for p in pf.positions] == ["BBAS3"]
    assert "?" not in [p.ticker for p in pf.positions]


@pytest.mark.asyncio
async def test_formato_irreconhecivel_falha_alto(monkeypatch):
    """Se NENHUMA posição tem símbolo, o formato mudou de novo. Estourar aqui faz o
    portfolio_service servir a última carteira em cache, em vez de seguir com uma
    carteira fantasma."""
    with pytest.raises(RuntimeError, match="formato"):
        await _parse(
            monkeypatch,
            [{"valueInBaseCurrency": 100.0}, {"valueInBaseCurrency": 200.0}],
        )


@pytest.mark.asyncio
async def test_carteira_vazia_nao_e_erro(monkeypatch):
    """Carteira sem holdings é estado legítimo, não falha de formato."""
    pf = await _parse(monkeypatch, [])

    assert pf.positions == []
    assert pf.total_value == 0
