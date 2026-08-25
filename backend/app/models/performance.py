"""Modelos da curva de rendimento (série semanal + índices)."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class WeeklyPoint(BaseModel):
    week_of: str = Field(..., description="Semana ISO 'yyyy-Www'.")
    week_end: str = Field(..., description="Domingo de fechamento (ISO).")
    captured_at: str
    late: bool = Field(False, description="Capturado fora da janela pretendida.")
    total_value: float
    rv_value: Optional[float] = None
    rf_value: Optional[float] = None
    flow_net: float = 0.0
    twr_period: Optional[float] = Field(None, description="Retorno do período (fração).")
    twr_cumulative: Optional[float] = Field(None, description="TWR acumulado (fração).")


class BenchmarkSeries(BaseModel):
    code: str
    label: str
    source: str
    proxy: Optional[str] = Field(
        None,
        description="Ticker usado como aproximação do índice — tem taxa e tracking error.",
    )
    values: List[Optional[float]] = Field(
        default_factory=list,
        description="Retorno acumulado em cada ponto da série, na mesma base do TWR.",
    )


class PerformanceResponse(BaseModel):
    """Curva de rendimento: TWR da carteira contra os índices.

    Só o TWR é comparado com índice. O XIRR responde outra pergunta ("quanto o MEU
    dinheiro rendeu") e por isso vem separado, sem par de comparação.
    """

    points: List[WeeklyPoint] = Field(default_factory=list)
    benchmarks: List[BenchmarkSeries] = Field(default_factory=list)
    composite_weights: Dict[str, float] = Field(
        default_factory=dict,
        description="Pesos do benchmark composto, derivados da carteira alvo do usuário.",
    )
    twr: Optional[float] = Field(None, description="TWR acumulado da janela (fração).")
    twr_annualized: Optional[float] = None
    xirr: Optional[float] = Field(
        None, description="Retorno ponderado pelo dinheiro, anualizado (fração)."
    )
    invested: float = Field(0.0, description="Aportes líquidos no período (BRL).")
    current_value: float = 0.0
    window: str = Field("all", description="Janela pedida: '3m' | '6m' | '12m' | 'all'.")
    gaps: List[str] = Field(
        default_factory=list, description="Semanas sem captura dentro da série."
    )
    warnings: List[str] = Field(default_factory=list)
    currency: str = "BRL"
