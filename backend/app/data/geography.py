"""Exposição geográfica default por ticker — mapa curado + heurística por sufixo.

Segue o precedente de `CLASS_BY_TICKER` e `SECTOR_BY_TICKER` em `watchlist.py`: um mapa
curado ganha do palpite, porque é justamente nos ETFs que o sufixo mente (IVVB11 e BOVA11
terminam igual e apontam para continentes diferentes).

**A classificação é por DOMICÍLIO DO ATIVO, não por origem da receita.** Uma empresa
brasileira que fatura quase tudo lá fora continua `BR`, e um FII que compra imóvel no
exterior continua `BR`. É uma convenção, não uma verdade econômica — a tela diz isso em
uma linha, e o usuário pode sobrescrever qualquer rótulo (inclusive com exposição parcial,
ver `weight` em `label_assignments`).

Nada aqui é gravado no banco: é o default que aparece quando o usuário não escolheu nada.
Por isso `resolve()` devolve também de ONDE veio o rótulo, para a interface distinguir o
que ela herdou do que ele decidiu.
"""
from __future__ import annotations

from typing import Literal

from app.util import normalize_ticker

Geography = Literal["BR", "INTL"]

# Sufixos de BDR (recibo de ação estrangeira). É a única heurística confiável por sufixo.
BDR_SUFFIXES = ("34", "35", "32", "33", "39")

_INTL_ETFS = (
    "IVVB11", "SPXI11", "NASD11", "EURP11", "ACWI11", "WRLD11", "BDRX11",
    "XINA11", "ASIA11", "GOLD11", "HASH11",
)

_BR_ETFS = (
    "BOVA11", "BOVV11", "BOVB11", "BOVX11", "PIBB11", "SMAL11", "DIVO11", "FIND11",
    "MATB11", "GOVE11", "ISUS11", "ECOO11", "AUVP11", "XFIX11",
    "IMAB11", "IB5M11", "B5P211", "IRFM11", "IMBB11", "FIXA11",
)

_BDRS = (
    "AAPL34", "MSFT34", "GOGL34", "AMZO34", "META34", "NFLX34", "TSLA34", "NVDC34",
    "JPMC34", "BERK34", "COCA34", "MCDC34", "VISA34", "WALM34", "JNJB34", "PGCO34",
    "DISB34", "ROXO34",
)

_BR_STOCKS = (
    "BBAS3", "ITSA4", "ITUB4", "BBDC4", "SANB11",
    "TAEE11", "ISAE4", "EGIE3", "CMIG4", "CPLE6", "AXIA3",
    "SBSP3", "SAPR11", "CSMG3",
    "BBSE3", "PSSA3", "CXSE3",
    "VIVT3", "TIMS3",
    "VALE3", "PETR4", "KLBN11", "FESA4", "WEGE3",
)

_BR_FIIS = (
    "MXRF11", "KNRI11", "HGLG11", "XPLG11", "VISC11", "HGRU11", "KNCR11", "BCFF11",
    "VGHF11", "RECR11", "HGRE11", "XPML11", "BTLG11", "VILG11", "MALL11", "KNIP11",
    "IRDM11", "HSML11", "RBRF11", "TRXF11",
)

# Mapa curado. Os ETFs são o motivo de o mapa existir; ações e FIIs entram para tornar o
# default determinístico nos tickers que o app já conhece, em vez de depender da heurística.
GEOGRAPHY_BY_TICKER: dict[str, Geography] = {
    **{t: "INTL" for t in _INTL_ETFS},
    **{t: "INTL" for t in _BDRS},
    **{t: "BR" for t in _BR_ETFS},
    **{t: "BR" for t in _BR_STOCKS},
    **{t: "BR" for t in _BR_FIIS},
}


def is_bdr_ticker(ticker: str) -> bool:
    """Sufixo de BDR: 4 letras + 2 dígitos, terminando em 34/35/32/33/39."""
    t = normalize_ticker(ticker)
    return len(t) >= 6 and t.endswith(BDR_SUFFIXES) and t[-2:].isdigit()


def resolve(ticker: str) -> tuple[Geography, str]:
    """Devolve (rótulo, origem) — origem em {'curated', 'suffix', 'fallback'}.

    O fallback é `BR` porque tudo aqui é negociado na B3: assumir domicílio brasileiro erra
    menos que assumir o contrário, e o erro que sobra (um ETF estrangeiro fora do mapa) é
    visível na tela e corrigível em um clique.
    """
    t = normalize_ticker(ticker)
    curated = GEOGRAPHY_BY_TICKER.get(t)
    if curated:
        return curated, "curated"
    if is_bdr_ticker(t):
        return "INTL", "suffix"
    return "BR", "fallback"


def default_geography(ticker: str) -> Geography:
    return resolve(ticker)[0]
