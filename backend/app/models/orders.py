"""Modelos de ordens executadas ('já comprei') e histórico."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class OrderIn(BaseModel):
    ticker: str
    asset_class: Optional[str] = None
    shares: int = Field(..., gt=0, description="Quantidade de cotas/ações compradas.")
    price: float = Field(..., gt=0, description="Preço pago por cota (BRL).")
    fees: float = Field(0.0, ge=0, description="Custos/corretagem (BRL).")
    executed_at: Optional[str] = Field(None, description="Data ISO (padrão: agora).")
    note: Optional[str] = None
    plan_id: Optional[int] = None


class OrderOut(BaseModel):
    id: int
    ticker: str
    asset_class: Optional[str] = None
    shares: int
    price: float
    fees: float = 0.0
    executed_at: Optional[str] = None
    note: Optional[str] = None
    plan_id: Optional[int] = None


class OrdersListResponse(BaseModel):
    items: List[OrderOut] = Field(default_factory=list)
    total_invested: float = 0.0
    currency: str = "BRL"
