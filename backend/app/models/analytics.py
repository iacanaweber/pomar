"""Modelos de renda passiva (renda estimada da carteira e Yield on Cost)."""
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
