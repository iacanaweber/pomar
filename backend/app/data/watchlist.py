"""Universo curado de candidatos da B3 (editável).

Mantemos uma lista enxuta de boas pagadoras e ativos líquidos em vez de varrer a B3
inteira — isso respeita a quota da brapi e mantém as recomendações relevantes. A lista
prioriza setores perenes (BESST de Barsi) e pagadoras consistentes (Bazin), além de FIIs,
ETFs e BDRs populares. Ajuste à vontade — é só dado.
"""
from __future__ import annotations

# Ações — foco em dividendos / setores perenes (Bancos, Energia, Saneamento, Seguros, Telecom)
STOCKS = [
    "BBAS3", "ITSA4", "ITUB4", "BBDC4", "SANB11",        # Bancos / financeiro
    "TAEE11", "ISAE4", "EGIE3", "CMIG4", "CPLE6", "ELET3",  # Energia (ISAE4 = ex-TRPL4)
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

