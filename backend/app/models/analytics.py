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


class IncomeResponse(BaseModel):
    annual_income: float = 0.0
    monthly_income: float = 0.0
    portfolio_yield: float = 0.0
    total_value: float = 0.0
    by_asset: List[IncomeAsset] = Field(default_factory=list)
    currency: str = "BRL"
    warnings: List[str] = Field(default_factory=list)


class ProjectionPoint(BaseModel):
    year: int
    value: float
    invested: float
    annual_income: float
    monthly_income: float


class ProjectionRequest(BaseModel):
    current_value: float = Field(0.0, ge=0)
    monthly_contribution: float = Field(0.0, ge=0)
    annual_yield: float = Field(..., ge=0, le=1, description="DY anual em fração (0..1).")
    annual_growth: float = Field(0.0, ge=0, le=1, description="Crescimento anual dos proventos (0..1).")
    years: int = Field(20, ge=1, le=80)
    reinvest: bool = True
    target_monthly_income: Optional[float] = Field(
        None, ge=0, description="Se informado, calcula o aporte mensal necessário para essa renda."
    )


class ProjectionResponse(BaseModel):
    series: List[ProjectionPoint] = Field(default_factory=list)
    final_value: float = 0.0
    final_monthly_income: float = 0.0
    total_invested: float = 0.0
    total_dividends: float = 0.0
    required_monthly_contribution: Optional[float] = None
