"""Tipos base do contrato de transparência.

Todo número que o backend expõe carrega de onde veio. A regra de ouro do projeto:
nada de "caixa-preta" — cada valor tem uma `key` (que aponta para o glossário) e
uma `source` legível (campo da brapi / Ghostfolio / fórmula calculada).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    """De onde veio um número exibido na tela."""

    key: str = Field(..., description="Chave no glossário (ex: 'pvp', 'div_yield').")
    source: str = Field(
        ..., description="Origem legível, ex: 'brapi:priceToBook' ou 'calculado: alvo - atual'."
    )
    stale: bool = Field(False, description="True se o valor veio de cache defasado.")
    as_of: Optional[str] = Field(None, description="Carimbo ISO de quando o dado foi obtido.")


class Metric(BaseModel):
    """Uma sub-métrica do score, com valor cru, normalizado e proveniência.

    `available=False` significa que a fonte não tinha o dado; nesse caso o peso é
    redistribuído entre as métricas disponíveis (ver services/scoring.py) e
    `fallback_used` explica qualquer aproximação aplicada.
    """

    key: str = Field(..., description="Identificador da métrica e chave no glossário.")
    label: str = Field(..., description="Rótulo curto para a UI (ex: 'P/VP').")
    raw_value: Optional[float] = Field(None, description="Valor cru, na unidade original.")
    display: Optional[str] = Field(None, description="Valor já formatado para exibição.")
    normalized: Optional[float] = Field(
        None, description="Valor normalizado em [0,1] (maior = melhor)."
    )
    weight: float = Field(..., description="Peso desta métrica no score composto (após renormalizar).")
    contribution: Optional[float] = Field(
        None, description="weight * normalized — quanto somou ao score final."
    )
    source: str = Field(..., description="Origem legível do dado.")
    available: bool = Field(True, description="False quando a fonte não tinha o dado.")
    fallback_used: Optional[str] = Field(
        None, description="Aproximação aplicada quando o dado ideal faltava."
    )
    peer_group: Optional[str] = Field(
        None, description="Grupo de pares usado na normalização (ex: 'FII/Logística')."
    )
