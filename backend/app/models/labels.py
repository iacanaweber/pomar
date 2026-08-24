"""Modelos dos rótulos e das atribuições por dimensão."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class LabelOut(BaseModel):
    id: int
    dimension: str = Field(..., description="'bucket' | 'indexer' | 'geography'.")
    code: str
    name: str
    builtin: bool = Field(False, description="Embutido — não pode ser removido.")


class LabelIn(BaseModel):
    dimension: str = Field(..., description="'bucket' | 'indexer' | 'geography'.")
    code: str = Field(..., description="Código curto, normalizado em MAIÚSCULAS (ex.: 'LCI').")
    name: Optional[str] = Field(None, description="Nome exibido. Vazio usa o próprio código.")


class AssignmentItem(BaseModel):
    label_id: int
    weight: float = Field(
        1.0,
        gt=0,
        description="Exposição parcial (ex.: 0.6 INTL + 0.4 BR). Os pesos da mesma dimensão "
        "somam 1.0; 'bucket' aceita um rótulo só e força peso 1.0.",
    )


class AssignmentsIn(BaseModel):
    """Substitui todas as atribuições de UMA dimensão para UM sujeito. Lista vazia limpa."""

    subject_type: Literal["ticker", "fi_account"]
    subject_id: str = Field(..., description="Ticker (normalizado) ou id da conta como texto.")
    dimension: str
    items: List[AssignmentItem] = Field(default_factory=list)


class AssignmentOut(BaseModel):
    subject_type: str
    subject_id: str
    dimension: str
    code: str
    name: str
    weight: float = 1.0
    source: str = Field(
        "user",
        description="'user' quando o usuário escolheu; 'curated'/'suffix'/'fallback' quando "
        "o rótulo é o default herdado do mapa de `data/geography.py`.",
    )
    id: Optional[int] = Field(None, description="Id da atribuição — nulo quando é default.")
    label_id: Optional[int] = None
