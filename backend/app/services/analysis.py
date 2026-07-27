"""Leitura FACTUAL de um ativo — sem nota, sem ranking, sem estratégia.

O Pomar não pontua ativos: a decisão de O QUE comprar é do usuário (carteira alvo) e a
de QUANTO comprar é aritmética de rebalanceamento (services/allocation.py). O que sobra
para este módulo são fatos calculáveis e auditáveis, cada um com fórmula explícita:

- **preço-teto de Bazin**: média dos proventos na janela de 5 anos ÷ DY-alvo. Diz se o
  preço de hoje está na zona de compra — informação ortogonal ao peso na carteira.
- **consistência** dos proventos: anos pagos ÷ anos analisados, penalizando cortes fortes.
- **crescimento (CAGR)** dos proventos na janela.
- **payout**: provento médio ÷ LPA.
- **red flags**: prejuízo, endividamento, payout insustentável, liquidez baixa, preço
  acima do teto, histórico irregular. Dado ausente é NEUTRO — nunca inventado.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.models.market import Asset
from app.models.plan import AssetAnalysis

BAZIN_TARGET_YIELD = 0.06  # DY-alvo de 6% do método Bazin (default; configurável)
BAZIN_MIN_PAID_YEARS = 3  # nº mínimo de anos pagos para calcular o preço-teto de Bazin
BAZIN_AVG_WINDOW = 5  # janela (anos) da média de proventos do preço-teto de Bazin
BAZIN_SELIC_FACTOR = 0.5  # modo dinâmico: exige DY ≥ 50% do CDI (piso = alvo manual)
CONSISTENCY_MIN_YEARS = 3  # histórico mínimo para medir consistência (evita 100% trivial)
ROE_GOOD = 0.15  # ROE consistente acima disto é sinal positivo (Barsi/Bazin)

# Limiar de endividamento para o PROXY Dív.Líq/EBIT do Fundamentus (EBIT < EBITDA →
# razão maior). Equivale a ~3/4 sobre EBITDA em empresas típicas.
DEBT_PROXY_PENALTY_START = 4.0
DEBT_PROXY_FLAG = 5.0

# Piso de liquidez média diária (R$) por classe — abaixo disso, é um alerta.
LIQUIDITY_MIN: Dict[str, float] = {
    "STOCK": 1_000_000.0, "FII": 200_000.0, "BDR": 500_000.0, "ETF": 200_000.0,
}


def resolve_bazin_target_yield(
    mode: Optional[str], manual: float = BAZIN_TARGET_YIELD, cdi: Optional[float] = None
) -> float:
    """DY-alvo de Bazin efetivo. 'fixed_6' (ou None) usa o manual; 'dynamic_selic' atrela à
    taxa livre de risco: max(manual, 0,5×CDI) — endurece o teto quando os juros sobem."""
    manual = manual or BAZIN_TARGET_YIELD
    if mode == "dynamic_selic" and cdi and cdi > 0:
        return round(max(manual, BAZIN_SELIC_FACTOR * cdi), 4)
    return round(manual, 4)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _bazin_paid_window(asset: Asset) -> List[float]:
    """Proventos > 0 dos últimos BAZIN_AVG_WINDOW anos (janela fixa, sem deflacionar por zeros)."""
    years = sorted(asset.dividends_by_year.keys())[-BAZIN_AVG_WINDOW:]
    return [v for y in years if (v := asset.dividends_by_year[y]) and v > 0]


def _bazin_ceiling_price(asset: Asset, target_yield: float = BAZIN_TARGET_YIELD) -> Optional[float]:
    """Preço-teto de Bazin em R$ = média dos proventos na janela de 5 anos ÷ DY-alvo.

    A média divide pela JANELA COMPLETA (anos sem pagamento contam como zero): quem pagou
    R$2 em 3 de 5 anos tem teto menor do que quem pagou todo ano — pagadora irregular não
    ganha teto de pagadora perene. Exige um mínimo de anos pagos (BAZIN_MIN_PAID_YEARS).
    None sem preço, sem histórico mínimo, ou DY-alvo inválido.
    """
    if not asset.price or target_yield <= 0:
        return None
    years = sorted(asset.dividends_by_year.keys())[-BAZIN_AVG_WINDOW:]
    if not years:
        return None
    values = [asset.dividends_by_year[y] or 0.0 for y in years]
    paid = [v for v in values if v > 0]
    if len(paid) < BAZIN_MIN_PAID_YEARS:
        return None
    ceiling = (sum(values) / len(values)) / target_yield
    return ceiling if ceiling > 0 else None


def _bazin_margin(asset: Asset, target_yield: float = BAZIN_TARGET_YIELD) -> Optional[float]:
    """Margem sobre o preço-teto de Bazin, em [-1, 1] (positivo = comprando abaixo do teto)."""
    ceiling = _bazin_ceiling_price(asset, target_yield)
    if ceiling is None or not asset.price:
        return None
    margin = (ceiling - asset.price) / ceiling
    return max(-1.0, min(1.0, margin))


def _dividend_consistency(asset: Asset) -> Optional[float]:
    """Anos pagos ÷ anos analisados, penalizando CORTES fortes (>50% a/a).

    Um corte de 90% no provento não pode manter consistência 1,0 — a nota mede
    perenidade, não presença. Cada corte >50% multiplica por 0,75.
    """
    years = asset.dividends_by_year
    if not years or len(years) < CONSISTENCY_MIN_YEARS:
        return None  # histórico curto não vira "100% consistente" trivial
    ordered = [years[y] or 0.0 for y in sorted(years)]
    paid = sum(1 for v in ordered if v > 0)
    base = paid / len(ordered)
    cuts = sum(1 for prev, cur in zip(ordered, ordered[1:]) if prev > 0 and cur < 0.5 * prev)
    return round(base * (0.75 ** cuts), 4)


def _dividend_cagr(asset: Asset) -> Optional[float]:
    """CAGR aproximado dos proventos na janela: média dos 2 últimos anos ÷ média dos 2
    primeiros, anualizada pelo intervalo entre os centros das janelas.

    None com histórico < 4 anos ou base zero (crescimento de quem não pagava não é
    mensurável — vira indisponível, nunca inventado).
    """
    years = sorted(asset.dividends_by_year)
    if len(years) < 4:
        return None
    vals = [asset.dividends_by_year[y] or 0.0 for y in years]
    first = (vals[0] + vals[1]) / 2
    last = (vals[-1] + vals[-2]) / 2
    if first <= 0:
        return None
    span = len(years) - 2  # distância entre os centros das duas janelas de 2 anos
    if span <= 0:
        return None
    return round((last / first) ** (1 / span) - 1, 4)


def _payout_ratio(asset: Asset) -> Optional[float]:
    """Payout médio aproximado = média dos proventos pagos (janela de 5 anos) ÷ LPA atual.

    Usa a média (não o último ano isolado, que é volátil). LPA é o do período corrente —
    aproximação assumida e documentada.
    """
    f = asset.fundamentals
    if f.lpa is None or f.lpa <= 0:
        return None
    paid = _bazin_paid_window(asset)
    if not paid:
        return None
    return (sum(paid) / len(paid)) / f.lpa


def _quality_assessment(
    asset: Asset,
    bazin_margin: Optional[float] = None,
    consistency: Optional[float] = None,
) -> tuple[str, List[str]]:
    """Selo de risco (verde|amarelo|vermelho) + red flags factuais.

    Dado ausente é NEUTRO (não penaliza) — distingue 'fonte ausente' de 'motivo ruim'.
    Sinaliza value traps: barata e pagando muito, mas endividada / com payout
    insustentável / com prejuízo / ilíquida.
    """
    f = asset.fundamentals
    q = 1.0
    flags: List[str] = []
    if f.pl is not None and f.pl <= 0:
        q *= 0.5
        flags.append("Empresa com prejuízo (P/L ≤ 0)")
    # O dado do Fundamentus é Dív.Líquida ÷ EBIT (proxy — EBIT < EBITDA, a razão sai
    # maior). Limiar calibrado para o proxy: 4/5, não os 3/4 clássicos de EBITDA —
    # senão utilities de capital intensivo (energia/saneamento) tomavam corte indevido
    # com dívida/EBITDA real na faixa saudável.
    if f.net_debt_to_ebitda is not None and f.net_debt_to_ebitda > DEBT_PROXY_PENALTY_START:
        q *= max(0.3, 1 - 0.15 * (f.net_debt_to_ebitda - DEBT_PROXY_PENALTY_START))
        if f.net_debt_to_ebitda > DEBT_PROXY_FLAG:
            flags.append("Endividamento elevado (dív. líq./EBIT, proxy)")
    payout = _payout_ratio(asset)
    # FII distribui ~95–100% do resultado por lei: payout alto é normal, não penaliza.
    if payout is not None and asset.asset_class != "FII":
        if payout > 1.0:
            q *= 0.6
            flags.append("Payout acima de 100% (dividendo pode não se sustentar)")
        elif payout > 0.8:
            q *= 0.85
            flags.append("Payout alto (acima de 80% do lucro)")
    liq_min = LIQUIDITY_MIN.get(asset.asset_class, 0.0)
    if f.avg_daily_liquidity is not None and f.avg_daily_liquidity < liq_min:
        q *= 0.7
        flags.append("Liquidez diária baixa")
    if bazin_margin is not None and bazin_margin < 0:
        flags.append("Negociando acima do preço-teto de Bazin")
    if consistency is not None and consistency < 0.5:
        flags.append("Histórico de dividendos irregular")
    q = _clamp(q)
    if q >= 0.85 and not flags:
        level = "verde"
    elif q < 0.6 or len(flags) >= 2:
        level = "vermelho"
    else:
        level = "amarelo"
    return level, flags


def _highlights(
    asset: Asset,
    margin: Optional[float],
    consistency: Optional[float],
    cagr: Optional[float],
) -> List[str]:
    """Fatos favoráveis do ativo — descrições, não recomendações."""
    out: List[str] = []
    if margin is not None and margin > 0:
        out.append(f"{margin * 100:.0f}% abaixo do preço-teto de Bazin")
    if consistency is not None and consistency >= 0.8:
        out.append("Histórico consistente de dividendos")
    if cagr is not None and cagr >= 0.03:
        out.append(f"Proventos crescendo ~{cagr * 100:.0f}% a.a.")
    if asset.fundamentals.roe is not None and asset.fundamentals.roe >= ROE_GOOD:
        out.append(f"ROE alto ({asset.fundamentals.roe * 100:.0f}%)")
    return out


def analyze_asset(asset: Asset, bazin_target_yield: float = BAZIN_TARGET_YIELD) -> AssetAnalysis:
    """Monta a leitura factual completa de um ativo (usada por /asset e pelo plano)."""
    ceiling = _bazin_ceiling_price(asset, bazin_target_yield)
    margin = _bazin_margin(asset, bazin_target_yield)
    consistency = _dividend_consistency(asset)
    cagr = _dividend_cagr(asset)
    payout = _payout_ratio(asset)
    level, flags = _quality_assessment(asset, margin, consistency)
    return AssetAnalysis(
        ticker=asset.ticker,
        name=asset.name,
        asset_class=asset.asset_class,
        sector=asset.sector,
        price=asset.price,
        dividend_yield=asset.fundamentals.dividend_yield,
        dividend_yield_net=asset.fundamentals.dividend_yield_net,
        bazin_ceiling_price=round(ceiling, 2) if ceiling is not None else None,
        bazin_below_ceiling=(
            None if (ceiling is None or asset.price is None) else asset.price <= ceiling
        ),
        bazin_margin=round(margin, 4) if margin is not None else None,
        bazin_target_yield=bazin_target_yield,
        dividend_consistency=consistency,
        dividend_cagr=cagr,
        payout_ratio=round(payout, 4) if payout is not None else None,
        risk_level=level,
        red_flags=flags,
        highlights=_highlights(asset, margin, consistency, cagr),
    )
