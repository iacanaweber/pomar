"""Modelos da carteira atual (lida do Ghostfolio, somente leitura)."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Position(BaseModel):
    ticker: str = Field(..., description="Símbolo do ativo (ex: 'BBAS3').")
    name: Optional[str] = Field(None, description="Nome do ativo, se disponível.")
    asset_class: str = Field("UNKNOWN", description="STOCK | FII | ETF | BDR | UNKNOWN.")
    sector: Optional[str] = Field(None, description="Setor, se conhecido.")
    value: float = Field(..., description="Valor de mercado da posição (BRL).")
    weight: float = Field(..., description="Peso na carteira (0..1).")
    quantity: Optional[float] = Field(None, description="Quantidade de cotas/ações.")
    cost_basis: Optional[float] = Field(None, description="Custo total da posição (BRL), se conhecido.")
    average_price: Optional[float] = Field(None, description="Preço médio de compra (BRL).")
    net_performance_pct: Optional[float] = Field(
        None, description="Rentabilidade líquida da posição (fração) — do Ghostfolio, se disponível."
    )
    source: str = Field("ghostfolio:holdings", description="Origem do dado.")


class Allocations(BaseModel):
    by_class: Dict[str, float] = Field(default_factory=dict, description="Peso por classe (0..1).")
    by_sector: Dict[str, float] = Field(default_factory=dict, description="Peso por setor (0..1).")


class Portfolio(BaseModel):
    total_value: float = Field(..., description="Valor total da carteira (BRL).")
    currency: str = Field("BRL", description="Moeda de referência.")
    positions: List[Position] = Field(default_factory=list)
    allocations: Allocations = Field(default_factory=Allocations)
    as_of: str = Field(..., description="Carimbo ISO da leitura.")
    source: str = Field("ghostfolio", description="Origem dos dados.")
    warnings: List[str] = Field(default_factory=list)
