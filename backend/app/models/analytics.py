"""Modelos de renda passiva (renda atual da carteira e projeção bola de neve)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class IncomeAsset(BaseModel):
    ticker: str
    name: Optional[str] = None
    value: float
    dividend_yield: float
    annual_income: float
    cost_basis: Optional[float] = None
    yield_on_cost: Optional[float] = Field(None, description="Renda anual ÷ preço médio pago.")


class IncomeResponse(BaseModel):
    # Números principais são LÍQUIDOS (JCP ×0,85) — o que efetivamente cai na conta.
    annual_income: float = 0.0
    monthly_income: float = 0.0
    annual_income_gross: Optional[float] = Field(None, description="Renda anual bruta (antes do IR do JCP).")
    monthly_income_gross: Optional[float] = Field(None, description="Renda mensal bruta (antes do IR do JCP).")
    portfolio_yield: float = 0.0
    yield_on_cost: Optional[float] = Field(None, description="YoC agregado (renda ÷ custo total).")
    total_value: float = 0.0
    by_asset: List[IncomeAsset] = Field(default_factory=list)
    currency: str = "BRL"
    warnings: List[str] = Field(default_factory=list)


class IncomeGoalResponse(BaseModel):
    """Objetivo de renda: quanto falta e quanto aportar para viver de dividendos.

    v4: meta comparada em reais DE HOJE (inflação das preferências), aporte projetado é o
    que sobra APÓS o desvio para a reserva, renda da reserva pode contar (opt-in) e há
    marcos intermediários ('próximos R$ 100/mês') para a jornada de décadas ter vitórias.
    """

    target_monthly_income: float = 0.0
    current_monthly_income: float = 0.0
    gap_monthly: float = 0.0
    pct_achieved: float = 0.0
    horizon_years: int = 20
    portfolio_yield: float = 0.0
    required_monthly_contribution: Optional[float] = None
    estimated_years_to_goal: Optional[int] = None
    expected_inflation: float = Field(0.0, description="Inflação anual usada (preferências).")
    reserve_monthly_income: Optional[float] = Field(
        None, description="Renda mensal estimada da reserva/RF (Σ saldo × último rendimento ÷ 12)."
    )
    include_reserve_income: bool = Field(False, description="Se a renda da RF conta na meta (opt-in).")
    aporte_rv_estimated: Optional[float] = Field(
        None, description="Aporte que sobra para RV após o desvio para a reserva (usado na projeção)."
    )
    next_milestone: Optional[float] = Field(None, description="Próximo marco de renda mensal (R$).")
    milestone_gap: Optional[float] = Field(None, description="Quanto falta de renda para o marco.")
    milestone_capital_needed: Optional[float] = Field(
        None, description="Capital adicional ~necessário para o marco (gap×12 ÷ yield)."
    )
    currency: str = "BRL"
    warnings: List[str] = Field(default_factory=list)


class SnapshotPoint(BaseModel):
    month: str  # yyyy-mm
    total_value: Optional[float] = None
    annual_income: Optional[float] = None
    monthly_income: Optional[float] = None
    portfolio_yield: Optional[float] = None
    yield_on_cost: Optional[float] = None


class YocPoint(BaseModel):
    month: str
    yoc: Optional[float] = None


class SnapshotsResponse(BaseModel):
    """Série mensal REAL da carteira (patrimônio, renda estimada, YoC) — a prova visual
    da bola de neve. Alimentada por um snapshot automático por mês."""

    months: List[SnapshotPoint] = Field(default_factory=list)
    currency: str = "BRL"


class RealizedMonth(BaseModel):
    month: str  # yyyy-mm
    total: float = 0.0


class RealizedAsset(BaseModel):
    ticker: str
    total: float = 0.0


class RealizedPayment(BaseModel):
    date: str  # yyyy-mm-dd
    ticker: str
    value: float


class RealizedIncomeResponse(BaseModel):
    """Renda REALIZADA: dividendos que efetivamente caíram na conta (fonte: Ghostfolio).

    É o contraponto da renda estimada (valor × DY): a série real da bola de neve.
    """

    months: List[RealizedMonth] = Field(default_factory=list, description="Últimos 24 meses.")
    total_12m: float = 0.0
    monthly_avg_12m: float = 0.0
    by_asset_12m: List[RealizedAsset] = Field(default_factory=list)
    last_payments: List[RealizedPayment] = Field(default_factory=list, description="Pagamentos mais recentes.")
    total_30d: float = Field(0.0, description="Recebido nos últimos 30 dias (base do reinvestimento).")
    currency: str = "BRL"
    warnings: List[str] = Field(default_factory=list)


class CalendarMonth(BaseModel):
    month: int  # 1..12
    income: float = 0.0
    by_asset: List[dict] = Field(default_factory=list)


class AnnouncedPayment(BaseModel):
    ticker: str
    payment_date: Optional[str] = Field(None, description="Data de pagamento (None = anunciado, a definir).")
    ex_date: Optional[str] = None
    value_per_share: float
    net_value_per_share: float
    type: Optional[str] = None
    quantity: Optional[float] = Field(None, description="Cotas na carteira.")
    total_net: Optional[float] = Field(None, description="R$ líquidos a receber (valor × cotas).")


class AnnouncedResponse(BaseModel):
    """Proventos futuros JÁ ANUNCIADOS para os ativos da carteira — agenda real, não sazonalidade."""

    items: List[AnnouncedPayment] = Field(default_factory=list)
    total_net: float = Field(0.0, description="Soma líquida do que já está anunciado.")
    currency: str = "BRL"
    warnings: List[str] = Field(default_factory=list)


class CalendarResponse(BaseModel):
    months: List[CalendarMonth] = Field(default_factory=list)
    annual_total: float = 0.0
    currency: str = "BRL"
    basis: str = "média sazonal dos últimos anos (estimativa, líquida de IR do JCP)"
    warnings: List[str] = Field(default_factory=list)


class ProjectionPoint(BaseModel):
    year: int
    value: float
    invested: float
    annual_income: float
    monthly_income: float
    monthly_income_real: Optional[float] = Field(
        None, description="Renda mensal em reais DE HOJE (deflacionada pela inflação esperada)."
    )


class ProjectionRequest(BaseModel):
    current_value: float = Field(0.0, ge=0)
    monthly_contribution: float = Field(0.0, ge=0)
    annual_yield: float = Field(..., ge=0, le=1, description="DY anual em fração (0..1).")
    # Cenário pessimista (proventos/patrimônio encolhendo) é permitido: ge=-0.5.
    annual_growth: float = Field(
        0.0, ge=-0.5, le=1,
        description="Crescimento anual do patrimônio que acompanha os proventos (-0.5..1).",
    )
    annual_inflation: float = Field(
        0.0, ge=0, le=0.5, description="Inflação anual esperada — deflaciona para reais de hoje."
    )
    years: int = Field(20, ge=1, le=80)
    reinvest: bool = True
    target_monthly_income: Optional[float] = Field(
        None, ge=0, description="Se informado, calcula o aporte mensal necessário para essa renda."
    )


class ProjectionResponse(BaseModel):
    series: List[ProjectionPoint] = Field(default_factory=list)
    final_value: float = 0.0
    final_monthly_income: float = 0.0
    final_monthly_income_real: Optional[float] = Field(
        None, description="Renda mensal final em reais de hoje (igual à nominal com inflação 0)."
    )
    total_invested: float = 0.0
    total_dividends: float = 0.0
    required_monthly_contribution: Optional[float] = None
