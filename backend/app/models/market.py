"""Modelos de dados de mercado (brapi.dev)."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Fundamentals(BaseModel):
    """Fundamentos de um ativo. Campos podem ser None quando a brapi não fornece."""

    pvp: Optional[float] = Field(None, description="Preço / Valor Patrimonial (priceToBook).")
    pl: Optional[float] = Field(None, description="Preço / Lucro (priceEarnings).")
    dividend_yield: Optional[float] = Field(
        None, description="Dividend yield BRUTO trailing-365d (0..1, ex: 0.092 = 9,2%)."
    )
    dividend_yield_net: Optional[float] = Field(
        None, description="Dividend yield LÍQUIDO (JCP×0,85; dividendo/FII isentos), trailing-365d."
    )
    lpa: Optional[float] = Field(None, description="Lucro por ação (base do Número de Graham).")
    vpa: Optional[float] = Field(None, description="Valor patrimonial por ação (base do Número de Graham).")
    market_cap: Optional[float] = Field(None, description="Valor de mercado.")
    # Eixo de risco/qualidade (anti value-trap). None = sem dado (tratado como neutro).
    roe: Optional[float] = Field(None, description="Return on equity (0..1).")
    net_margin: Optional[float] = Field(None, description="Margem líquida (0..1).")
    net_debt_to_ebitda: Optional[float] = Field(None, description="Dívida líquida / EBITDA.")
    current_ratio: Optional[float] = Field(None, description="Liquidez corrente (ativo circ./passivo circ.).")
    avg_daily_liquidity: Optional[float] = Field(None, description="Volume financeiro médio diário (R$).")


class Asset(BaseModel):
    ticker: str
    name: Optional[str] = None
    asset_class: str = Field("UNKNOWN", description="STOCK | FII | ETF | BDR.")
    sector: Optional[str] = None
    price: Optional[float] = Field(None, description="Cotação mais recente (BRL).")
    fundamentals: Fundamentals = Field(default_factory=Fundamentals)
    dividends_by_year: Dict[str, float] = Field(
        default_factory=dict,
        description="Soma de dividendos por ano (ex: {'2023': 1.2, '2024': 1.4}). Base para "
        "preço-teto de Bazin e consistência.",
    )
    lot_size: int = Field(1, description="Tamanho do lote padrão (FII/ETF normalmente 1).")
    missing: List[str] = Field(
        default_factory=list, description="Quais dados faltaram nesta consulta."
    )
    stale: bool = Field(False, description="True se veio de cache defasado.")
    as_of: Optional[str] = Field(None, description="Carimbo ISO da cotação/fundamentos.")
    source: str = Field("brapi", description="Origem dos dados.")
