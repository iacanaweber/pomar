"""Filtros de ELEGIBILIDADE por estratégia (fidelidade ao método, não só pesos).

Os métodos clássicos são, em grande parte, sobre QUEM entra no universo — não só sobre
o peso das métricas. Aqui cada estratégia define um filtro: dado o ativo e suas métricas
já calculadas, devolve None se elegível ou uma frase com o motivo da exclusão.

Só estratégias explícitas filtram; "equilibrado" não filtra (experiência padrão intacta).
Dado ausente NÃO exclui por si (evita esvaziar o ranking quando a fonte falha) — exceto
onde o próprio método exige o dado (ex.: Graham exige lucro positivo).
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from app.models.common import Metric
from app.models.market import Asset

EligibilityFilter = Callable[[Asset, Dict[str, Metric]], Optional[str]]


def _avail(mbk: Dict[str, Metric], key: str) -> Optional[Metric]:
    m = mbk.get(key)
    return m if (m is not None and m.available) else None


# Liquidez média diária mínima que Barsi exige para montar posição relevante por décadas.
BARSI_MIN_LIQUIDITY = 5_000_000.0


def _barsi(asset: Asset, mbk: Dict[str, Metric]) -> Optional[str]:
    besst = _avail(mbk, "sector_besst")
    if besst is None or (besst.raw_value or 0) < 1:
        return "Fora dos setores perenes (BESST) de Barsi"
    cons = _avail(mbk, "dividend_consistency")
    if cons is None or (cons.raw_value or 0) < 0.8:
        return "Consistência de dividendos insuficiente para Barsi"
    liq = asset.fundamentals.avg_daily_liquidity
    if liq is not None and liq < BARSI_MIN_LIQUIDITY:
        return "Liquidez diária abaixo do mínimo de Barsi (R$ 5 mi/dia)"
    return None


def _graham(asset: Asset, mbk: Dict[str, Metric]) -> Optional[str]:
    f = asset.fundamentals
    if f.pl is None or f.pl <= 0:
        return "Sem lucro positivo (Graham exige lucros)"
    g = _avail(mbk, "graham")
    if g is None or (g.raw_value or 999) > 22.5:
        return "P/L × P/VP acima de 22,5 (Graham)"
    if f.current_ratio is not None and f.current_ratio < 1.5:
        return "Liquidez corrente baixa para o investidor defensivo de Graham"
    return None


def _bazin(asset: Asset, mbk: Dict[str, Metric]) -> Optional[str]:
    cons = _avail(mbk, "dividend_consistency")
    if cons is None or (cons.raw_value or 0) < 0.8:
        return "Consistência de dividendos insuficiente para Bazin"
    bz = _avail(mbk, "bazin_ceiling")
    if bz is None or (bz.raw_value or -1) <= 0:
        return "Negociando acima do preço-teto de Bazin"
    return None


def _dividend_growth(asset: Asset, mbk: Dict[str, Metric]) -> Optional[str]:
    cons = _avail(mbk, "dividend_consistency")
    if cons is None or (cons.raw_value or 0) < 0.6:
        return "Histórico de proventos insuficiente para crescimento de dividendos"
    # O preset agora exige o que o nome promete: proventos de fato CRESCENDO.
    g = _avail(mbk, "dividend_growth")
    if g is None:
        return "Sem histórico suficiente para medir o crescimento dos proventos"
    if (g.raw_value or 0) <= 0:
        return "Proventos estagnados ou em queda na janela de 5 anos"
    return None


STRATEGY_FILTERS: Dict[str, EligibilityFilter] = {
    "barsi": _barsi,
    "graham": _graham,
    "bazin": _bazin,
    "dividend_growth": _dividend_growth,
}


def eligibility_reason(
    strategy: Optional[str], asset: Asset, metrics_by_key: Dict[str, Metric]
) -> Optional[str]:
    """Motivo de exclusão do ativo pela estratégia, ou None se elegível (ou sem filtro)."""
    flt = STRATEGY_FILTERS.get(strategy or "")
    return flt(asset, metrics_by_key) if flt else None
