"""Índices de comparação: quais são, de onde vêm e como viram retorno de uma janela.

Guardamos o **NÍVEL** do índice na data, nunca a variação. Com o nível dá para recalcular
o retorno de qualquer janela depois; com a variação, a janela fica presa à que foi gravada.

**De onde vem cada um.** Ibovespa, CDI, IPCA e dólar têm fonte oficial. IFIX, IMA-B e
IRF-M não têm API pública gratuita, então usamos **ETFs listados na B3 como proxy** — e a
tela diz isso, porque um ETF tem taxa de administração e tracking error, e apresentá-lo
como se fosse o índice seria mentir por omissão. O S&P 500 entra por um ETF brasileiro
(IVVB11), o que o deixa **em reais** de propósito: é o que o usuário efetivamente ganha,
já com o câmbio embutido. O USD/BRL vai junto para quem quiser separar as duas coisas.

**O CDI é série de FATOR DIÁRIO, não de nível.** Ele precisa ser acumulado
multiplicativamente (não somado) para virar um índice base 100. O IPCA é variação mensal
e segue a mesma regra.

Falha de índice nunca impede o snapshot da carteira: cada série é buscada de forma
independente e o que não veio simplesmente não é gravado naquela data.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

# code -> (rótulo, fonte, é proxy?)
BENCHMARKS: Dict[str, Dict[str, Any]] = {
    "IBOV": {"label": "Ibovespa", "source": "brapi ^BVSP", "proxy": None},
    "CDI": {"label": "CDI", "source": "BCB SGS 12", "proxy": None},
    "IPCA": {"label": "IPCA", "source": "BCB SGS 433", "proxy": None},
    "USDBRL": {"label": "Dólar", "source": "BCB SGS 1", "proxy": None},
    "IFIX": {"label": "IFIX", "source": "brapi XFIX11", "proxy": "XFIX11"},
    "IMAB": {"label": "IMA-B", "source": "brapi IMAB11", "proxy": "IMAB11"},
    "IRFM": {"label": "IRF-M", "source": "brapi IRFM11", "proxy": "IRFM11"},
    "SP500BRL": {"label": "S&P 500 (em reais)", "source": "brapi IVVB11", "proxy": "IVVB11"},
}

# Índices que vêm de um ticker da brapi (o nível é a própria cotação).
_BRAPI_TICKERS = {
    "IBOV": "^BVSP",
    "IFIX": "XFIX11",
    "IMAB": "IMAB11",
    "IRFM": "IRFM11",
    "SP500BRL": "IVVB11",
}

# Séries do Banco Central. O CDI é % ao dia útil e o IPCA é % ao mês: os dois precisam ser
# ACUMULADOS para virar nível. O dólar já é um nível.
SGS_CDI, SGS_IPCA, SGS_USD = 12, 433, 1

# Mapa classe -> índice do benchmark COMPOSTO. É o único comparável metodologicamente
# defensável: confronta a execução da estratégia com a estratégia. O Ibovespa entra na
# tela como referência cultural, não como critério.
CLASS_BENCHMARK = {
    "STOCK": "IBOV",
    "FII": "IFIX",
    "BDR": "SP500BRL",
    "ETF": "IBOV",       # refinado por geografia em `composite_weights`
    "RENDA_FIXA": "CDI",  # refinado por indexador
}


def compose_weights(
    targets: Dict[str, float],
    etf_geography: Optional[Dict[str, float]] = None,
    rf_indexers: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """Pesos do benchmark composto a partir da carteira ALVO do usuário.

    Dois refinamentos, porque duas classes não têm um índice único que as represente:

    * **ETF** se divide pela geografia: a parcela internacional vai para o S&P em reais e
      a brasileira para o Ibovespa. Sem isso, um IVVB11 seria comparado com o Ibovespa.
    * **RENDA_FIXA** se divide pelo indexador: o que está em IPCA vai para o IMA-B, o
      prefixado para o IRF-M, o resto para o CDI. Comparar uma carteira de IPCA+ com o CDI
      esconde justamente o risco que ela assume.
    """
    geo = etf_geography or {}
    idx = rf_indexers or {}
    out: Dict[str, float] = {}

    def add(code: str, w: float) -> None:
        if w > 0:
            out[code] = round(out.get(code, 0.0) + w, 6)

    for cls, peso in (targets or {}).items():
        peso = max(0.0, float(peso or 0.0))
        if peso <= 0:
            continue
        if cls == "ETF":
            intl = max(0.0, min(1.0, float(geo.get("INTL", 0.0))))
            add("SP500BRL", peso * intl)
            add("IBOV", peso * (1.0 - intl))
        elif cls == "RENDA_FIXA":
            total = sum(max(0.0, v) for v in idx.values()) or 0.0
            if total <= 0:
                add("CDI", peso)
                continue
            for code, v in idx.items():
                fatia = peso * max(0.0, v) / total
                if code == "IPCA":
                    add("IMAB", fatia)
                elif code == "PREFIXADO":
                    add("IRFM", fatia)
                else:
                    add("CDI", fatia)
        else:
            alvo = CLASS_BENCHMARK.get(cls)
            if alvo:
                add(alvo, peso)

    soma = sum(out.values())
    if soma > 0:
        out = {k: round(v / soma, 6) for k, v in out.items()}
    return out


def accumulate(rates_pct: Sequence[Dict[str, Any]], base: float = 100.0) -> List[Dict[str, Any]]:
    """Série de % (ao dia útil ou ao mês) -> série de NÍVEL base 100.

    Acumula MULTIPLICANDO. Somar percentuais é o erro clássico com o CDI: 252 dias a
    0,05% somam 12,6%, mas capitalizam 13,4% — e a diferença cresce com a janela.
    """
    nivel = base
    out: List[Dict[str, Any]] = []
    for obs in rates_pct:
        try:
            v = float(obs["value"])
        except (KeyError, TypeError, ValueError):
            continue
        nivel *= 1.0 + v / 100.0
        d = obs["date"]
        out.append({"date": d.isoformat() if hasattr(d, "isoformat") else str(d)[:10],
                    "level": round(nivel, 8)})
    return out


def level_at(series: Sequence[Dict[str, Any]], when: date) -> Optional[float]:
    """Nível na data, ou o último ANTERIOR a ela.

    "Último anterior" e não "mais próximo": o índice pode não ter observação no domingo
    do fechamento (não há pregão), e usar um valor do FUTURO para fechar uma semana
    passada é justamente o tipo de contaminação que a série congelada existe para evitar.
    """
    alvo = when.isoformat()
    melhor = None
    for obs in series:
        d = str(obs.get("obs_date") or obs.get("date"))[:10]
        if d <= alvo:
            melhor = obs
        else:
            break
    if melhor is None:
        return None
    try:
        return float(melhor["level"])
    except (KeyError, TypeError, ValueError):
        return None


def window_return(
    series: Sequence[Dict[str, Any]], start: date, end: date
) -> Optional[float]:
    """Retorno do índice entre duas datas, a partir dos NÍVEIS. `None` se faltar ponta."""
    a = level_at(series, start)
    b = level_at(series, end)
    if a is None or b is None or a <= 0:
        return None
    return round(b / a - 1.0, 8)


def cumulative_series(
    series: Sequence[Dict[str, Any]], dates: Sequence[date]
) -> List[Optional[float]]:
    """Retorno acumulado do índice em cada data, com base na PRIMEIRA data da janela.

    É o formato que o gráfico consome: todas as séries partindo de zero no mesmo ponto,
    que é o que torna a comparação com o TWR da carteira legível.
    """
    if not dates:
        return []
    base = level_at(series, dates[0])
    out: List[Optional[float]] = []
    for d in dates:
        nivel = level_at(series, d)
        out.append(
            round(nivel / base - 1.0, 8) if (base and base > 0 and nivel is not None) else None
        )
    return out


def composite_series(
    weights: Dict[str, float], by_code: Dict[str, Sequence[Dict[str, Any]]],
    dates: Sequence[date],
) -> List[Optional[float]]:
    """Retorno acumulado do benchmark COMPOSTO — média ponderada dos componentes.

    Renormaliza entre os componentes que de fato têm dado na data: sem isso, um índice
    que falhou puxaria o composto para baixo como se tivesse rendido zero.
    """
    out: List[Optional[float]] = []
    per_code = {code: cumulative_series(by_code.get(code, []), dates) for code in weights}
    for i, _ in enumerate(dates):
        soma_peso = 0.0
        acc = 0.0
        for code, peso in weights.items():
            v = per_code[code][i] if i < len(per_code[code]) else None
            if v is None:
                continue
            acc += peso * v
            soma_peso += peso
        out.append(round(acc / soma_peso, 8) if soma_peso > 0 else None)
    return out


def business_day_before(d: date) -> date:
    """Sexta anterior quando `d` cai no fim de semana — para pedir cotação a quem só tem
    pregão em dia útil."""
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d
