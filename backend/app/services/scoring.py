"""Motor de score do Pomar — transparente e ancorado em grandes investidores.

Quatro famílias de métricas, cada uma com peso configurável (presets de estratégia):

- valuation  -> desconto / Graham      : P/VP, P/L, Margem Graham (vs teto 22,5), Nº de Graham
- dividend   -> renda recorrente        : dividend yield, margem Bazin (preço-teto 6%), consistência
- rebalance  -> meta de carteira        : gap entre peso-alvo e peso-atual da classe
- sector     -> setores perenes (Barsi) : afinidade com BESST (bancos, energia, saneamento, seguros, telecom)

Normalização HÍBRIDA (v2):
- "anchor": métricas com "preço justo" conhecido (Graham vs 22,5; Nº de Graham) são pontuadas pela
  DISTÂNCIA ao justo — o teto deixa de ser decorativo e passa a valer no score.
- "pct": percentil DENTRO da classe, agora SEM auto-inclusão e com mid-rank em empates (escala [0,1]).
- "raw": valor já em 0..1 (consistência, rebalance, setor).

Regras de ouro:
- Dado faltante nunca é inventado: a métrica vira `available=False` e seu peso é redistribuído.
- P/L<=0 (prejuízo) não é "desconto": vira indisponível, coerente com o Número de Graham.
- Média de Bazin só sobre anos efetivamente pagos (não deflaciona por anos sem pagamento).
"""
from __future__ import annotations

from math import sqrt
from typing import Callable, Dict, List, Optional

from app.config import SECTOR_AFFINITY_MAP
from app.models.common import Metric
from app.models.market import Asset
from app.models.portfolio import Portfolio
from app.models.scoring import ScoredAsset
from app.services.strategies import eligibility_reason

BAZIN_TARGET_YIELD = 0.06  # DY-alvo de 6% do método Bazin (default; configurável)
GRAHAM_CEILING = 22.5  # teto clássico de P/L × P/VP
BAZIN_MIN_PAID_YEARS = 3  # nº mínimo de anos pagos para calcular o preço-teto de Bazin
BAZIN_AVG_WINDOW = 5  # janela (anos) da média de proventos do preço-teto de Bazin
CONSISTENCY_MIN_YEARS = 3  # histórico mínimo para medir consistência (evita 100% trivial)
ROE_GOOD = 0.15  # ROE consistente acima disto é sinal positivo (Barsi/Bazin)
SECTOR_PEER_MIN = 4  # mínimo de pares no setor para normalizar por setor (senão, por classe)

# Piso de liquidez média diária (R$) por classe — abaixo disso, penaliza o score.
LIQUIDITY_MIN: Dict[str, float] = {
    "STOCK": 1_000_000.0, "FII": 200_000.0, "BDR": 500_000.0, "ETF": 200_000.0,
}


BAZIN_SELIC_FACTOR = 0.5  # modo dinâmico: exige DY ≥ 50% do CDI (piso = alvo manual)


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


def _graham_anchor(raw: float) -> float:
    """Margem de Graham por DISTÂNCIA ao teto: (22,5 − P/L×P/VP) / 22,5, em [0,1].

    Zera acima do teto (sem margem de segurança) — fiel ao critério absoluto de Graham,
    ao contrário de um percentil que premiaria a "menos cara" de um grupo todo caro.
    """
    return _clamp((GRAHAM_CEILING - raw) / GRAHAM_CEILING)


# Especificação das métricas. `norm`: "anchor" (distância ao justo) | "pct" (percentil intra-classe)
# | "raw" (valor já em 0..1). `anchor` é a função aplicada quando norm == "anchor".
_METRIC_SPECS: List[dict] = [
    {"key": "pvp", "label": "P/VP", "family": "valuation", "classes": {"STOCK", "FII"},
     "higher_better": False, "norm": "pct"},
    {"key": "pl", "label": "P/L", "family": "valuation", "classes": {"STOCK"},
     "higher_better": False, "norm": "pct", "subweight": 0.6},
    {"key": "graham", "label": "Margem Graham", "family": "valuation", "classes": {"STOCK"},
     "higher_better": True, "norm": "anchor", "anchor": _graham_anchor, "subweight": 0.7},
    {"key": "graham_intrinsic", "label": "Margem (Nº de Graham)", "family": "valuation",
     "classes": {"STOCK"}, "higher_better": True, "norm": "raw", "subweight": 0.7},
    # DY e Margem Bazin medem quase a mesma coisa (renda÷preço) → subpeso 0.5 cada, para que
    # juntas não dominem a família e a CONSISTÊNCIA (perenidade) tenha peso real.
    {"key": "div_yield", "label": "Dividend Yield", "family": "dividend",
     "classes": {"STOCK", "FII", "ETF", "BDR"}, "higher_better": True, "norm": "pct", "subweight": 0.5},
    {"key": "bazin_ceiling", "label": "Margem Bazin", "family": "dividend",
     "classes": {"STOCK", "FII"}, "higher_better": True, "norm": "pct", "subweight": 0.5},
    {"key": "dividend_consistency", "label": "Consistência de dividendos", "family": "dividend",
     "classes": {"STOCK", "FII"}, "higher_better": True, "norm": "raw"},
    {"key": "rebalance_gap", "label": "Rebalanceamento", "family": "rebalance",
     "classes": {"STOCK", "FII", "ETF", "BDR"}, "higher_better": True, "norm": "raw"},
    {"key": "sector_besst", "label": "Setor perene (BESST)", "family": "sector",
     "classes": {"STOCK"}, "higher_better": True, "norm": "raw"},
]

_FAMILIES = ["valuation", "dividend", "rebalance", "sector"]

_PERCENT_KEYS = {
    "div_yield", "bazin_ceiling", "rebalance_gap", "dividend_consistency",
    "sector_besst", "graham_intrinsic",
}


def _fmt(key: str, raw: Optional[float]) -> Optional[str]:
    if raw is None:
        return None
    if key == "div_yield":
        return f"{raw * 100:.1f}%"
    if key in _PERCENT_KEYS:
        return f"{raw * 100:.0f}%"
    return f"{raw:.2f}"


def _besst_affinity(sector: Optional[str]) -> Optional[float]:
    """Afinidade GRADUADA com BESST em [0,1] (mapa setor→afinidade, maior casamento).

    Setor ausente => None (indisponível). Setor presente sem casar => 0.0. Resolve o
    "financ" amplo demais da v2: corretora/fintech recebem 0.3, não 1.0 — só bancos = 1.0.
    """
    if not sector:
        return None
    s = sector.strip().lower()
    best = 0.0
    for kw, aff in SECTOR_AFFINITY_MAP.items():
        if kw in s:
            best = max(best, aff)
    return best


def _bazin_paid_window(asset: Asset) -> list[float]:
    """Proventos > 0 dos últimos BAZIN_AVG_WINDOW anos (janela fixa, sem deflacionar por zeros)."""
    years = sorted(asset.dividends_by_year.keys())[-BAZIN_AVG_WINDOW:]
    return [v for y in years if (v := asset.dividends_by_year[y]) and v > 0]


def _bazin_ceiling_price(asset: Asset, target_yield: float = BAZIN_TARGET_YIELD) -> Optional[float]:
    """Preço-teto de Bazin em R$ = média dos proventos pagos (janela de 5 anos) ÷ DY-alvo.

    None sem preço, sem histórico mínimo de anos pagos, ou DY-alvo inválido.
    """
    if not asset.price or target_yield <= 0:
        return None
    paid = _bazin_paid_window(asset)
    if len(paid) < BAZIN_MIN_PAID_YEARS:
        return None
    ceiling = (sum(paid) / len(paid)) / target_yield
    return ceiling if ceiling > 0 else None


def _bazin_margin(asset: Asset, target_yield: float = BAZIN_TARGET_YIELD) -> Optional[float]:
    """Margem sobre o preço-teto de Bazin, em [-1, 1] (positivo = comprando abaixo do teto)."""
    ceiling = _bazin_ceiling_price(asset, target_yield)
    if ceiling is None or not asset.price:
        return None
    margin = (ceiling - asset.price) / ceiling
    return max(-1.0, min(1.0, margin))


def _graham_intrinsic_margin(asset: Asset) -> Optional[float]:
    """Margem de segurança pelo Número de Graham: (√(22,5·LPA·VPA) − preço) ÷ valor intrínseco.

    Em [0,1]. Indisponível sem LPA/VPA positivos (prejuízo/patrimônio negativo não tem
    valor intrínseco de Graham).
    """
    f = asset.fundamentals
    if not asset.price or f.lpa is None or f.vpa is None or f.lpa <= 0 or f.vpa <= 0:
        return None
    intrinsic = sqrt(GRAHAM_CEILING * f.lpa * f.vpa)
    if intrinsic <= 0:
        return None
    return _clamp((intrinsic - asset.price) / intrinsic)


def _dividend_consistency(asset: Asset) -> Optional[float]:
    years = asset.dividends_by_year
    if not years or len(years) < CONSISTENCY_MIN_YEARS:
        return None  # histórico curto não vira "100% consistente" trivial
    paid = sum(1 for v in years.values() if v and v > 0)
    return paid / len(years)


def _graham_value(asset: Asset) -> Optional[float]:
    pvp = asset.fundamentals.pvp
    pl = asset.fundamentals.pl
    if pvp is None or pl is None or pl <= 0 or pvp <= 0:
        return None
    return pl * pvp  # menor é melhor; convertido em margem pela âncora ao teto 22,5


def _pl_value(asset: Asset) -> Optional[float]:
    """P/L só como sinal de desconto quando positivo. P/L<=0 (prejuízo) não é 'barato'."""
    pl = asset.fundamentals.pl
    return pl if (pl is not None and pl > 0) else None


def _raw_values(
    asset: Asset, class_gap: float, bazin_target_yield: float = BAZIN_TARGET_YIELD
) -> Dict[str, Optional[float]]:
    return {
        "pvp": asset.fundamentals.pvp if (asset.fundamentals.pvp or 0) > 0 else None,
        "pl": _pl_value(asset),
        "graham": _graham_value(asset),
        "graham_intrinsic": _graham_intrinsic_margin(asset),
        "div_yield": asset.fundamentals.dividend_yield,
        "bazin_ceiling": _bazin_margin(asset, bazin_target_yield),
        "dividend_consistency": _dividend_consistency(asset),
        "rebalance_gap": class_gap,
        "sector_besst": _besst_affinity(asset.sector),
    }


def _percentile(value: float, peers: List[float], higher_better: bool) -> float:
    """Percentil de rank em [0,1], EXCLUINDO o próprio ativo e com mid-rank em empates.

    Corrige o viés de auto-inclusão (o pior ativo recebia 1/N em vez de ~0) e a compressão
    da escala. `peers` inclui o próprio valor; removemos uma ocorrência antes de comparar.
    """
    valid = [p for p in peers if p is not None]
    if len(valid) <= 1:
        return 0.5  # sem pares suficientes: neutro
    others = list(valid)
    try:
        others.remove(value)  # exclui uma ocorrência do próprio ativo
    except ValueError:
        pass
    n = len(others)
    if n == 0:
        return 0.5
    if higher_better:
        better = sum(1 for o in others if value > o)
    else:
        better = sum(1 for o in others if value < o)
    ties = sum(1 for o in others if o == value)
    return (better + 0.5 * ties) / n


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


def _quality_assessment(asset: Asset, metrics_by_key: Dict[str, Metric]) -> tuple[float, str, List[str]]:
    """Eixo de QUALIDADE/RISCO — separado das 4 famílias (não dilui o score; multiplica-o).

    Retorna (Q em [0,1], selo verde|amarelo|vermelho, red_flags). Dado ausente é NEUTRO
    (não penaliza) — distingue 'fonte ausente' de 'motivo ruim'. Afunda value traps
    (barato + paga muito, mas endividado / payout insustentável / prejuízo / ilíquido).
    """
    f = asset.fundamentals
    q = 1.0
    flags: List[str] = []
    if f.pl is not None and f.pl <= 0:
        q *= 0.5
        flags.append("Empresa com prejuízo (P/L ≤ 0)")
    if f.net_debt_to_ebitda is not None and f.net_debt_to_ebitda > 3:
        q *= max(0.3, 1 - 0.15 * (f.net_debt_to_ebitda - 3))
        if f.net_debt_to_ebitda > 4:
            flags.append("Endividamento elevado (dív. líq./EBITDA)")
    payout = _payout_ratio(asset)
    # FII distribui ~95–100% do resultado por lei: payout alto é normal, não penaliza.
    if payout is not None and asset.asset_class != "FII":
        if payout > 1.0:
            q *= 0.6
            flags.append("Payout acima de 100% (dividendo pode não se sustentar)")
        elif payout > 0.8:
            q *= 0.85
            flags.append("Payout alto (acima de 80% do lucro)")
    if f.avg_daily_liquidity is not None and f.avg_daily_liquidity < LIQUIDITY_MIN.get(asset.asset_class, 0.0):
        q *= 0.7
        flags.append("Liquidez diária baixa")
    bz = metrics_by_key.get("bazin_ceiling")
    if bz is not None and bz.available and (bz.raw_value or 0) < 0:
        flags.append("Negociando acima do preço-teto de Bazin")
    cons = metrics_by_key.get("dividend_consistency")
    if cons is not None and cons.available and (cons.raw_value or 1) < 0.5:
        flags.append("Histórico de dividendos irregular")
    q = _clamp(q)
    if q >= 0.85 and not flags:
        level = "verde"
    elif q < 0.6 or len(flags) >= 2:
        level = "vermelho"
    else:
        level = "amarelo"
    return q, level, flags


def score_assets(
    assets: List[Asset],
    portfolio: Portfolio,
    targets: Dict[str, float],
    weights: Dict[str, float],
    strategy: Optional[str] = None,
    bazin_target_yield: float = BAZIN_TARGET_YIELD,
) -> List[ScoredAsset]:
    """Pontua e ordena os ativos candidatos. Não aloca dinheiro (isso é da allocation)."""
    current_by_class = portfolio.allocations.by_class

    # gap de rebalanceamento por classe, normalizado em 0..1 (clampa negativos).
    raw_gaps = {
        cls: max(0.0, targets.get(cls, 0.0) - current_by_class.get(cls, 0.0))
        for cls in set(list(targets) + list(current_by_class))
    }
    max_gap = max(raw_gaps.values()) if raw_gaps else 0.0

    # 1) valores crus por ativo
    per_asset_raw: Dict[str, Dict[str, Optional[float]]] = {}
    for a in assets:
        cls = a.asset_class
        gap = raw_gaps.get(cls, 0.0)
        gap_norm = (gap / max_gap) if max_gap > 0 else 0.0
        per_asset_raw[a.ticker] = _raw_values(a, gap_norm, bazin_target_yield)

    # 2) pares para o percentil: por SETOR quando há massa suficiente (>= SECTOR_PEER_MIN),
    #    senão por CLASSE (banco vs banco, não banco vs mineradora; setor raro cai p/ classe).
    pct_specs = [s for s in _METRIC_SPECS if s["norm"] == "pct"]
    sector_counts: Dict[tuple, int] = {}
    for spec in pct_specs:
        for a in assets:
            if per_asset_raw[a.ticker][spec["key"]] is not None and a.sector:
                k = (spec["key"], a.sector)
                sector_counts[k] = sector_counts.get(k, 0) + 1

    def _peer_key(metric_key: str, asset: Asset) -> tuple:
        if asset.sector and sector_counts.get((metric_key, asset.sector), 0) >= SECTOR_PEER_MIN:
            return (metric_key, "sector", asset.sector)
        return (metric_key, "class", asset.asset_class)

    peers: Dict[tuple, List[float]] = {}
    for spec in pct_specs:
        for a in assets:
            v = per_asset_raw[a.ticker][spec["key"]]
            if v is None:
                continue
            peers.setdefault(_peer_key(spec["key"], a), []).append(v)

    results: List[ScoredAsset] = []
    for a in assets:
        cls = a.asset_class
        raw = per_asset_raw[a.ticker]

        applicable = [s for s in _METRIC_SPECS if cls in s["classes"]]
        built: List[dict] = []
        for spec in applicable:
            v = raw[spec["key"]]
            available = v is not None
            normalized: Optional[float] = None
            peer_group: Optional[str] = None
            if available:
                norm = spec["norm"]
                if norm == "pct":
                    pk = _peer_key(spec["key"], a)
                    peer_group = pk[2] if pk[1] == "sector" else cls
                    normalized = _percentile(v, peers.get(pk, []), spec["higher_better"])
                elif norm == "anchor":
                    anchor: Callable[[float], float] = spec["anchor"]
                    normalized = anchor(v)
                else:  # "raw" — valor já em 0..1
                    normalized = _clamp(v if spec["higher_better"] else 1 - v)
            built.append({"spec": spec, "raw": v, "available": available,
                          "normalized": normalized, "peer_group": peer_group})

        # redistribui pesos: família sem métrica disponível cede peso às demais; dentro da
        # família, o peso é dividido pelos SUBPESOS das métricas disponíveis (não igualmente).
        subw_by_family: Dict[str, float] = {f: 0.0 for f in _FAMILIES}
        for b in built:
            if b["available"]:
                subw_by_family[b["spec"]["family"]] += b["spec"].get("subweight", 1.0)
        total_family_weight = sum(
            weights.get(f, 0.0) for f in _FAMILIES if subw_by_family[f] > 0
        )

        metrics: List[Metric] = []
        composite = 0.0
        for b in built:
            spec = b["spec"]
            fam = spec["family"]
            if b["available"] and total_family_weight > 0 and subw_by_family[fam] > 0:
                w = weights.get(fam, 0.0) * (spec.get("subweight", 1.0) / subw_by_family[fam]) / total_family_weight
            else:
                w = 0.0
            contribution = (b["normalized"] or 0.0) * w if b["available"] else None
            if contribution:
                composite += contribution
            metrics.append(
                Metric(
                    key=spec["key"],
                    label=spec["label"],
                    raw_value=b["raw"],
                    display=_fmt(spec["key"], b["raw"]),
                    normalized=b["normalized"],
                    weight=round(w, 4),
                    contribution=round(contribution, 4) if contribution is not None else None,
                    source=_source_for(spec["key"]),
                    available=b["available"],
                    peer_group=b["peer_group"],
                )
            )

        applicable_count = len(applicable)
        available_count = sum(1 for b in built if b["available"])
        metrics_by_key = {m.key: m for m in metrics}
        q, risk_level, red_flags = _quality_assessment(a, metrics_by_key)
        final_score = round(composite * q, 4)
        elig = eligibility_reason(strategy, a, metrics_by_key)
        if elig:
            # fora dos critérios da estratégia escolhida: não é comprável (score 0), com motivo
            final_score = 0.0
            red_flags = [f"Não elegível ({strategy}): {elig}", *red_flags]

        # preço-teto de Bazin (R$) exposto para a UI
        ceiling_price = _bazin_ceiling_price(a, bazin_target_yield)
        bz_metric = metrics_by_key.get("bazin_ceiling")
        bz_margin = bz_metric.raw_value if (bz_metric and bz_metric.available) else None
        below = ceiling_price is not None and a.price is not None and a.price <= ceiling_price

        results.append(
            ScoredAsset(
                ticker=a.ticker,
                name=a.name,
                asset_class=cls,
                sector=a.sector,
                composite_score=final_score,
                composite_base=round(composite, 4),
                quality_factor=round(q, 4),
                risk_level=risk_level,
                red_flags=red_flags,
                metrics=metrics,
                data_completeness=f"{available_count}/{applicable_count}",
                reasons=_reasons(metrics, a),
                bazin_ceiling_price=round(ceiling_price, 2) if ceiling_price is not None else None,
                bazin_below_ceiling=below if ceiling_price is not None else None,
                bazin_margin=round(bz_margin, 4) if bz_margin is not None else None,
            )
        )

    results.sort(key=lambda r: r.composite_score, reverse=True)
    for i, r in enumerate(results, start=1):
        r.rank = i
    return results


def _source_for(key: str) -> str:
    return {
        "pvp": "Fundamentus (P/VP)",
        "pl": "Fundamentus (P/L, >0)",
        "graham": "calculado: distância de P/L×P/VP ao teto 22,5 (Graham)",
        "graham_intrinsic": "calculado: √(22,5×LPA×VPA) vs preço (Número de Graham, Fundamentus)",
        "div_yield": "calculado: proventos recentes (StatusInvest) ÷ preço",
        "bazin_ceiling": "calculado: preço-teto = média de proventos pagos ÷ 6% (Bazin/StatusInvest)",
        "dividend_consistency": "calculado: anos pagos ÷ anos analisados (StatusInvest)",
        "rebalance_gap": "calculado: alvo − atual (Ghostfolio)",
        "sector_besst": "calculado: setor (Fundamentus) ∈ BESST (Barsi)",
    }.get(key, "calculado")


def _reasons(metrics: List[Metric], asset: Asset) -> List[str]:
    """Frases curtas explicando por que o ativo está bem ranqueado (maiores contribuições)."""
    out: List[str] = []
    by_key = {m.key: m for m in metrics if m.available}
    if "sector_besst" in by_key and (by_key["sector_besst"].raw_value or 0) >= 1:
        out.append(f"Setor perene de dividendos (BESST): {asset.sector}")
    if "bazin_ceiling" in by_key and (by_key["bazin_ceiling"].raw_value or 0) > 0:
        out.append("Negociando abaixo do preço-teto de Bazin")
    if "graham" in by_key and (by_key["graham"].raw_value or 99) <= GRAHAM_CEILING:
        out.append(f"P/L × P/VP = {by_key['graham'].raw_value:.1f} (≤ 22,5 de Graham)")
    if "graham_intrinsic" in by_key and (by_key["graham_intrinsic"].raw_value or 0) > 0:
        out.append("Preço abaixo do valor intrínseco (Número de Graham)")
    if "dividend_consistency" in by_key and (by_key["dividend_consistency"].raw_value or 0) >= 0.8:
        out.append("Histórico consistente de dividendos")
    if asset.fundamentals.roe is not None and asset.fundamentals.roe >= ROE_GOOD:
        out.append(f"ROE alto ({asset.fundamentals.roe * 100:.0f}%)")
    if "rebalance_gap" in by_key and (by_key["rebalance_gap"].normalized or 0) >= 0.6:
        out.append(f"Classe {asset.asset_class} está sub-alocada vs sua meta")
    ranked = sorted(
        [m for m in metrics if m.contribution], key=lambda m: m.contribution, reverse=True
    )
    if not out and ranked:
        out.append(f"Destaque em {ranked[0].label.lower()}")
    return out[:3]
