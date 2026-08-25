"""Universo curado de candidatos da B3 (editável).

Mantemos uma lista enxuta de pagadoras e ativos líquidos em vez de varrer a B3 inteira —
isso respeita a quota da brapi e mantém as sugestões da watchlist relevantes. A seleção
favorece setores de receita previsível (bancos, energia, saneamento, seguros, telecom) e
pagadoras regulares, além de FIIs, ETFs e BDRs populares. Ajuste à vontade — é só dado.
"""
from __future__ import annotations

# Ações — foco em dividendos / setores perenes (Bancos, Energia, Saneamento, Seguros, Telecom)
STOCKS = [
    "BBAS3", "ITSA4", "ITUB4", "BBDC4", "SANB11",        # Bancos / financeiro
    "TAEE11", "ISAE4", "EGIE3", "CMIG4", "CPLE6", "AXIA3",  # Energia (ISAE4=ex-TRPL4, AXIA3=ex-ELET3)
    "SBSP3", "SAPR11", "CSMG3",                            # Saneamento
    "BBSE3", "PSSA3", "CXSE3",                             # Seguros
    "VIVT3", "TIMS3",                                      # Telecom
    "VALE3", "PETR4", "KLBN11", "FESA4", "WEGE3",          # Outros líquidos / dividendos
]

# FIIs — tijolo e papel populares
FIIS = [
    "MXRF11", "KNRI11", "HGLG11", "XPLG11", "VISC11",
    "HGRU11", "KNCR11", "BCFF11", "VGHF11", "RECR11",
]

# ETFs
ETFS = ["BOVA11", "IVVB11", "SMAL11", "DIVO11", "FIND11"]

# BDRs (exposição internacional)
BDRS = ["AAPL34", "MSFT34", "GOGL34", "AMZO34", "ROXO34"]


def default_universe() -> list[str]:
    return STOCKS + FIIS + ETFS + BDRS


# Classe conhecida de cada ticker da watchlist (mais confiável que adivinhar pelo sufixo,
# já que Units como TAEE11/SAPR11 terminam em 11 mas são ações, não FIIs).
CLASS_BY_TICKER: dict[str, str] = {
    **{t: "STOCK" for t in STOCKS},
    **{t: "FII" for t in FIIS},
    **{t: "ETF" for t in ETFS},
    **{t: "BDR" for t in BDRS},
}

# Setor canônico por ticker (determinístico, imune à grafia do provedor). Os rótulos dos
# setores BESST casam com BESST_KEYWORDS (Bancos/Energia/Saneamento/Seguros/Telecom), então
# a afinidade de setor perene fica estável. ETFs/BDRs (que o Fundamentus não cobre) recebem
# um rótulo de carteira útil: amplos -> "Diversificado", índice estrangeiro -> "Exterior".
SECTOR_BY_TICKER: dict[str, str] = {
    # Bancos
    "BBAS3": "Bancos", "ITUB4": "Bancos", "BBDC4": "Bancos", "SANB11": "Bancos", "ITSA4": "Bancos",
    # Energia
    "TAEE11": "Energia Elétrica", "ISAE4": "Energia Elétrica", "EGIE3": "Energia Elétrica",
    "CMIG4": "Energia Elétrica", "CPLE6": "Energia Elétrica", "AXIA3": "Energia Elétrica",
    # Saneamento
    "SBSP3": "Saneamento", "SAPR11": "Saneamento", "CSMG3": "Saneamento",
    # Seguros
    "BBSE3": "Seguros", "PSSA3": "Seguros", "CXSE3": "Seguros",
    # Telecom
    "VIVT3": "Telecom", "TIMS3": "Telecom",
    # Outros líquidos (não-BESST)
    "VALE3": "Mineração", "PETR4": "Petróleo e Gás", "KLBN11": "Papel e Celulose",
    "FESA4": "Siderurgia e Metalurgia", "WEGE3": "Bens Industriais",
    # ETFs (curados; amplos = Diversificado, índice estrangeiro = Exterior)
    "BOVA11": "Diversificado", "AUVP11": "Diversificado", "WRLD11": "Diversificado",
    "IVVB11": "Exterior", "NASD11": "Exterior", "HASH11": "Cripto",
    "SMAL11": "Small Caps", "DIVO11": "Dividendos", "FIND11": "Financeiro",
    # BDRs (exposição internacional)
    "AAPL34": "Exterior", "MSFT34": "Exterior", "GOGL34": "Exterior",
    "AMZO34": "Exterior", "ROXO34": "Exterior",
}

