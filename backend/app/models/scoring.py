"""Modelos do score e da resposta do plano de aporte."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.common import Metric
from app.models.market import Asset

# Classes que recebem aporte de renda variável (FIXED_INCOME fica com a reserva).
INVESTABLE_CLASSES = ("STOCK", "FII", "ETF", "BDR")
FOCUS_CHOICES = ("BALANCE",) + INVESTABLE_CLASSES


def validate_focus(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = value.strip().upper()
    if v not in FOCUS_CHOICES:
        raise ValueError(f"focus deve ser um de {', '.join(FOCUS_CHOICES)}; recebi '{value}'.")
    return v


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
    # Preço-teto de Bazin (valor absoluto), para a UI mostrar "abaixo/acima do teto".
    bazin_ceiling_price: Optional[float] = Field(
        None, description="Preço-teto de Bazin em BRL (dividendo médio ÷ DY-alvo). None se indisponível."
    )
    bazin_below_ceiling: Optional[bool] = Field(
        None, description="True se o preço atual está abaixo do teto (zona de compra)."
    )
    bazin_margin: Optional[float] = Field(
        None, description="Margem sobre o teto em [-1,1] (positivo = comprando com desconto)."
    )


class ReserveSuggestion(BaseModel):
    """Quanto do aporte direcionar à reserva/renda fixa antes da renda variável (Barsi/Bazin)."""

    target_amount: float = Field(..., description="Alvo de reserva em BRL (reserve_target × patrimônio).")
    current_amount: float = Field(..., description="Reserva atual (BRL) — do rastreador de renda fixa.")
    gap: float = Field(..., description="Quanto falta para a reserva-alvo (BRL).")
    pct_filled: float = Field(..., description="Fração da reserva-alvo já preenchida (0..1).")
    directed_now: float = Field(..., description="Quanto deste aporte vai para a reserva (BRL).")
    benchmark_cdi_annual: Optional[float] = Field(None, description="CDI anualizado (fração), referência.")
    note: str = Field("Complete a reserva/CDI antes da renda variável.")


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
    reserve: Optional[ReserveSuggestion] = Field(
        None, description="Sugestão de reserva/renda fixa (quando há reserve_target)."
    )
    warnings: List[str] = Field(default_factory=list)
    focus: Optional[str] = Field(
        None, description="Foco usado no plano: 'BALANCE' ou uma classe (STOCK/FII/ETF/BDR)."
    )
    plan_id: Optional[int] = Field(None, description="Id do plano persistido (plan_history).")
    created_at: Optional[str] = Field(None, description="Quando o plano foi gerado (planos salvos).")
    disclaimer: str = Field(
        "Conteúdo educativo. Não é recomendação de investimento. "
        "Os dados podem estar defasados; confira antes de operar.",
    )


class PlanSummary(BaseModel):
    """Resumo de um plano salvo (lista 'Planos anteriores')."""

    id: int
    created_at: Optional[str] = None
    aporte: Optional[float] = None
    strategy: Optional[str] = None
    suggested_count: Optional[int] = None


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
    max_weight_per_class: Optional[float] = Field(
        None, gt=0, le=1, description="Teto de peso por classe na carteira resultante."
    )
    reserve_target: Optional[float] = Field(
        None, ge=0, le=1, description="Fração-alvo em reserva/renda fixa. Se omitido, usa as preferências."
    )
    reserve_current: Optional[float] = Field(
        None, ge=0, description="Reserva já existente (BRL). Se omitido, usa o total do rastreador de RF."
    )
    allow_empty_portfolio: bool = Field(
        False,
        description="Permite gerar plano SEM conseguir ler a carteira (fail-open explícito). "
        "Por padrão o plano é abortado: alocar dinheiro real sobre carteira vazia produz "
        "sugestões materialmente erradas.",
    )
    focus: Optional[str] = Field(
        None,
        description="Foco do aporte: 'BALANCE' distribui entre as classes conforme as metas; "
        "uma classe (STOCK/FII/ETF/BDR) concentra todo o aporte de RV nela. "
        "Se omitido, usa a preferência salva.",
    )

    @field_validator("focus")
    @classmethod
    def _focus_valido(cls, v: Optional[str]) -> Optional[str]:
        return validate_focus(v)
