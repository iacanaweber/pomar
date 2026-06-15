"""Motor de score do Pomar — transparente e ancorado em grandes investidores.

Quatro famílias de métricas, cada uma com peso configurável (presets de estratégia):

- valuation  -> desconto / Graham      : P/VP, P/L, P/L×P/VP (≤ 22,5)
- dividend   -> renda recorrente        : dividend yield, margem Bazin (preço-teto 6%), consistência
- rebalance  -> meta de carteira        : gap entre peso-alvo e peso-atual da classe
- sector     -> setores perenes (Barsi) : afinidade com BESST (bancos, energia, saneamento, seguros, telecom)

Regras de ouro:
- Normalização por percentil DENTRO da classe (robusta a outliers, explicável).
- Dado faltante nunca é inventado: a métrica vira `available=False` e seu peso é
  redistribuído entre as métricas disponíveis do ativo.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.config import BESST_KEYWORDS
from app.models.common import Metric
from app.models.market import Asset
from app.models.portfolio import Portfolio
from app.models.scoring import ScoredAsset

BAZIN_TARGET_YIELD = 0.06  # DY-alvo de 6% do método Bazin
GRAHAM_CEILING = 22.5  # teto clássico de P/L × P/VP

# Especificação das métricas: família, classes aplicáveis e se "maior é melhor".
# `pct=True` => normaliza por percentil entre pares; senão usa o valor cru (já em 0..1).
_METRIC_SPECS = [
    {"key": "pvp", "label": "P/VP", "family": "valuation", "classes": {"STOCK", "FII"},
     "higher_better": False, "pct": True},
    {"key": "pl", "label": "P/L", "family": "valuation", "classes": {"STOCK"},
     "higher_better": False, "pct": True},
    {"key": "graham", "label": "Margem Graham", "family": "valuation", "classes": {"STOCK"},
     "higher_better": False, "pct": True},
    {"key": "div_yield", "label": "Dividend Yield", "family": "dividend",
     "classes": {"STOCK", "FII", "ETF", "BDR"}, "higher_better": True, "pct": True},
    {"key": "bazin_ceiling", "label": "Margem Bazin", "family": "dividend",
     "classes": {"STOCK", "FII"}, "higher_better": True, "pct": True},
    {"key": "dividend_consistency", "label": "Consistência de dividendos", "family": "dividend",
     "classes": {"STOCK", "FII"}, "higher_better": True, "pct": False},
    {"key": "rebalance_gap", "label": "Rebalanceamento", "family": "rebalance",
     "classes": {"STOCK", "FII", "ETF", "BDR"}, "higher_better": True, "pct": False},
    {"key": "sector_besst", "label": "Setor perene (BESST)", "family": "sector",
     "classes": {"STOCK"}, "higher_better": True, "pct": False},
]

_FAMILIES = ["valuation", "dividend", "rebalance", "sector"]


def _fmt(key: str, raw: Optional[float]) -> Optional[str]:
    if raw is None:
        return None
    if key in ("div_yield",):
        return f"{raw * 100:.1f}%"
    if key in ("bazin_ceiling", "rebalance_gap", "dividend_consistency", "sector_besst"):
        return f"{raw * 100:.0f}%"
    return f"{raw:.2f}"


def _besst_affinity(sector: Optional[str]) -> Optional[float]:
    if not sector:
        return None
    s = sector.strip().lower()
    return 1.0 if any(kw in s for kw in BESST_KEYWORDS) else 0.0


def _bazin_margin(asset: Asset) -> tuple[Optional[float], Optional[str]]:
    """Margem sobre o preço-teto de Bazin. Retorna (margem, fallback_used).

    Preço-teto = dividendo médio anual ÷ 6%. Margem = (teto − preço) ÷ teto, ou seja
    o quanto o preço está abaixo do teto (positivo = comprando barato).
    """
    price = asset.price
    if not price:
        return None, None
    avg_div: Optional[float] = None
    fallback: Optional[str] = None
    if asset.dividends_by_year:
        vals = [v for v in asset.dividends_by_year.values() if v is not None]
        if vals:
            avg_div = sum(vals) / len(vals)
    if avg_div is None and asset.fundamentals.dividend_yield:
        # Sem histórico: aproxima pelo provento implícito no yield dos últimos 12m.
        avg_div = asset.fundamentals.dividend_yield * price
        fallback = "yield_12m (sem histórico anual)"
    if not avg_div:
        return None, None
    ceiling = avg_div / BAZIN_TARGET_YIELD
    if ceiling <= 0:
        return None, fallback
    margin = (ceiling - price) / ceiling
    return max(-1.0, min(1.0, margin)), fallback


def _dividend_consistency(asset: Asset) -> Optional[float]:
    years = asset.dividends_by_year
    if not years:
        return None
    paid = sum(1 for v in years.values() if v and v > 0)
    return paid / len(years)


def _graham_value(asset: Asset) -> Optional[float]:
    pvp = asset.fundamentals.pvp
    pl = asset.fundamentals.pl
    if pvp is None or pl is None or pl <= 0 or pvp <= 0:
        return None
    return pl * pvp  # menor é melhor; comparado ao teto 22,5


def _raw_values(asset: Asset, class_gap: float) -> Dict[str, Optional[float]]:
    bazin, _ = _bazin_margin(asset)
    return {
        "pvp": asset.fundamentals.pvp,
        "pl": asset.fundamentals.pl,
        "graham": _graham_value(asset),
        "div_yield": asset.fundamentals.dividend_yield,
        "bazin_ceiling": bazin,
        "dividend_consistency": _dividend_consistency(asset),
        "rebalance_gap": class_gap,
        "sector_besst": _besst_affinity(asset.sector),
    }


def _percentile(value: float, peers: List[float], higher_better: bool) -> float:
    valid = [p for p in peers if p is not None]
    if len(valid) <= 1:
        return 0.5  # sem pares suficientes: neutro
    if higher_better:
        cnt = sum(1 for p in valid if value >= p)
    else:
        cnt = sum(1 for p in valid if value <= p)
    return cnt / len(valid)


def score_assets(
    assets: List[Asset],
    portfolio: Portfolio,
    targets: Dict[str, float],
    weights: Dict[str, float],
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
        raw = _raw_values(a, gap_norm)
        per_asset_raw[a.ticker] = raw

    # 2) arrays de pares por classe para métricas de percentil
    peers: Dict[tuple, List[float]] = {}
    for spec in _METRIC_SPECS:
        if not spec["pct"]:
            continue
        for a in assets:
            v = per_asset_raw[a.ticker][spec["key"]]
            if v is None:
                continue
            peers.setdefault((spec["key"], a.asset_class), []).append(v)

    results: List[ScoredAsset] = []
    for a in assets:
        cls = a.asset_class
        raw = per_asset_raw[a.ticker]

        # 2a) monta métricas disponíveis e aplicáveis
        applicable = [s for s in _METRIC_SPECS if cls in s["classes"]]
        built: List[dict] = []
        for spec in applicable:
            v = raw[spec["key"]]
            available = v is not None
            normalized: Optional[float] = None
            if available:
                if spec["pct"]:
                    normalized = _percentile(v, peers.get((spec["key"], cls), []), spec["higher_better"])
                else:
                    # valor cru já em 0..1 (consistência, setor, rebalance)
                    normalized = max(0.0, min(1.0, v if spec["higher_better"] else 1 - v))
            built.append({"spec": spec, "raw": v, "available": available, "normalized": normalized})

        # 2b) redistribui pesos: família sem métrica disponível cede peso às demais
        avail_by_family: Dict[str, int] = {f: 0 for f in _FAMILIES}
        for b in built:
            if b["available"]:
                avail_by_family[b["spec"]["family"]] += 1
        total_family_weight = sum(
            weights.get(f, 0.0) for f in _FAMILIES if avail_by_family[f] > 0
        )

        metrics: List[Metric] = []
        composite = 0.0
        bazin_fallback = _bazin_margin(a)[1]
        for b in built:
            spec = b["spec"]
            fam = spec["family"]
            if b["available"] and total_family_weight > 0 and avail_by_family[fam] > 0:
                w = (weights.get(fam, 0.0) / avail_by_family[fam]) / total_family_weight
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
                    fallback_used=bazin_fallback if spec["key"] == "bazin_ceiling" else None,
                    peer_group=cls if spec["pct"] else None,
                )
            )

        applicable_count = len(applicable)
        available_count = sum(1 for b in built if b["available"])
        results.append(
            ScoredAsset(
                ticker=a.ticker,
                name=a.name,
                asset_class=cls,
                sector=a.sector,
                composite_score=round(composite, 4),
                metrics=metrics,
                data_completeness=f"{available_count}/{applicable_count}",
                reasons=_reasons(metrics, a),
            )
        )

    results.sort(key=lambda r: r.composite_score, reverse=True)
    for i, r in enumerate(results, start=1):
        r.rank = i
    return results


def _source_for(key: str) -> str:
    return {
        "pvp": "brapi:priceToBook",
        "pl": "brapi:priceEarnings",
        "graham": "calculado: P/L × P/VP vs 22,5 (Graham)",
        "div_yield": "brapi:dividendYield",
        "bazin_ceiling": "calculado: preço-teto = dividendo ÷ 6% (Bazin)",
        "dividend_consistency": "calculado: anos pagos ÷ anos analisados",
        "rebalance_gap": "calculado: alvo − atual (Ghostfolio)",
        "sector_besst": "calculado: setor ∈ BESST (Barsi)",
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
    if "dividend_consistency" in by_key and (by_key["dividend_consistency"].raw_value or 0) >= 0.8:
        out.append("Histórico consistente de dividendos")
    if "rebalance_gap" in by_key and (by_key["rebalance_gap"].normalized or 0) >= 0.6:
        out.append(f"Classe {asset.asset_class} está sub-alocada vs sua meta")
    # ordena pela contribuição para mostrar primeiro o que mais pesou
    ranked = sorted(
        [m for m in metrics if m.contribution], key=lambda m: m.contribution, reverse=True
    )
    if not out and ranked:
        out.append(f"Destaque em {ranked[0].label.lower()}")
    return out[:3]
