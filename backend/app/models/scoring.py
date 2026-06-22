"""Modelos do score e da resposta do plano de aporte."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.common import Metric
from app.models.market import Asset


class SuggestedBuy(BaseModel):
    """Quanto comprar de um ativo — com a aritmética completa, auditável."""

    target_amount: float = Field(..., description="Valor-alvo a aportar neste ativo (BRL).")
    price: Optional[float] = Field(None, description="Cotação usada no cálculo (BRL).")
    shares: int = Field(0, description="Número inteiro de cotas/ações sugerido.")
    invested_exact: float = Field(0.0, description="shares * price — gasto real estimado.")
    lot_size: int = Field(1, description="Tamanho do lote considerado.")
    lot_note: Optional[str] = Field(None, description="Observação sobre lote/arredondamento.")


class ScoredAsset(BaseModel):
    ticker: str
    name: Optional[str] = None
    asset_class: str = "UNKNOWN"
    sector: Optional[str] = None
    rank: int = 0
    composite_score: float = Field(..., description="Score final (0..1), média ponderada das métricas.")
    metrics: List[Metric] = Field(default_factory=list)
    data_completeness: str = Field(
        "0/0", description="Métricas disponíveis vs totais, ex: '3/4'."
    )
    suggested: Optional[SuggestedBuy] = None
    reasons: List[str] = Field(
        default_factory=list, description="Frases curtas explicando por que o ativo subiu no ranking."
    )
    composite_base: float = Field(
        0.0, description="Score antes do fator de qualidade/risco (auditoria)."
    )
    quality_factor: float = Field(
        1.0, description="Fator de qualidade/risco em [0,1] que multiplica o score (1 = sem penalidade)."
    )
    risk_level: str = Field("verde", description="Selo de risco: verde | amarelo | vermelho.")
    red_flags: List[str] = Field(
        default_factory=list, description="Pontos de atenção (por que NÃO comprar)."
    )


class PlanResponse(BaseModel):
    aporte: float
    currency: str = "BRL"
    as_of: str
    weights: Dict[str, float] = Field(
        default_factory=dict, description="Pesos usados no score (visíveis para a UI)."
    )
    targets_by_class: Dict[str, float] = Field(default_factory=dict)
    current_by_class: Dict[str, float] = Field(default_factory=dict)
    ranking: List[ScoredAsset] = Field(default_factory=list)
    unallocated: float = Field(0.0, description="Sobra do aporte não alocada (BRL).")
    warnings: List[str] = Field(default_factory=list)
    disclaimer: str = Field(
        "Conteúdo educativo. Não é recomendação de investimento. "
        "Os dados podem estar defasados; confira antes de operar.",
    )


class AssetDetailResponse(BaseModel):
    """Detalhe de um ativo: dados crus (fundamentos, proventos) + a pontuação explicada."""

    asset: Asset
    scored: ScoredAsset


class PlanRequest(BaseModel):
    aporte: float = Field(..., gt=0, description="Quanto você tem para investir hoje (BRL).")
    strategy: str = Field(
        "equilibrado",
        description="Preset de estratégia: 'equilibrado' | 'barsi' | 'bazin' | 'graham'.",
    )
    targets: Optional[Dict[str, float]] = Field(
        None, description="Alvos de alocação por classe (0..1). Se omitido, usa o default."
    )
    weights: Optional[Dict[str, float]] = Field(
        None,
        description="Pesos das famílias de métricas (valuation/dividend/rebalance/sector). "
        "Se informado, sobrepõe o preset.",
    )
    max_assets: int = Field(5, ge=1, le=20, description="Máximo de ativos diferentes no plano.")
    max_weight_per_asset: float = Field(
        0.20, gt=0, le=1, description="Teto do peso de um ativo na carteira resultante."
    )
    min_ticket: float = Field(
        100.0, ge=0, description="Valor mínimo para alocar em um único ativo (BRL)."
    )
