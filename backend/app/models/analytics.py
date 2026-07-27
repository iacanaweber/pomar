"""Modelos de renda passiva (renda estimada da carteira, renda realizada e YoC)."""
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


class YocPoint(BaseModel):
    month: str
    yoc: Optional[float] = None


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
