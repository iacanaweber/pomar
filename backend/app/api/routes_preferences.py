"""Rotas de preferências do usuário (persistidas em SQLite)."""
from __future__ import annotations

from datetime import date
from typing import Dict, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.deps import get_db
from app.data.labels_seed import DIMENSIONS
from app.models.plan import ALLOCATION_CLASSES
from app.repositories import preferences_repo

router = APIRouter()


class PreferencesBody(BaseModel):
    """Campos opcionais — só os enviados são atualizados (patch)."""

    aporte_default: Optional[float] = None
    targets: Optional[dict] = None
    min_ticket: Optional[float] = None
    lot_mode: Optional[str] = None
    reserve_target: Optional[float] = Field(
        None,
        deprecated=True,
        description="APOSENTADO: era a fração do patrimônio em renda fixa. Virou o peso da "
        "classe RENDA_FIXA (em `targets`) mais o piso em R$ (`reserve_floor_amount`).",
    )
    bazin_target_mode: Optional[str] = None
    bazin_target_yield: Optional[float] = None
    class_targets: Optional[Dict[str, Dict[str, float]]] = None
    reserve_floor_amount: Optional[float] = Field(
        None, ge=0, description="Piso da reserva em R$ — o mínimo que fica em renda fixa LÍQUIDA."
    )
    reserve_floor_date: Optional[str] = Field(
        None, description="Data-base do piso (ISO). É de onde a correção pelo IPCA parte."
    )
    reserve_floor_index: Optional[Literal["none", "ipca"]] = Field(
        None, description="'ipca' corrige o piso pela inflação; 'none' o deixa nominal."
    )
    dimension_targets: Optional[Dict[str, Dict[str, float]]] = Field(
        None,
        description="Metas das dimensões SECUNDÁRIAS ({'geography': {'INTL': 0.2}}). "
        "Informativas: não têm efeito algum sobre a compra.",
    )
    legacy_in_total: Optional[bool] = Field(
        None,
        description="Se os ativos fora da carteira alvo entram no patrimônio que serve de "
        "base para os alvos em R$ das demais classes.",
    )
    reserve_floor_share: Optional[float] = Field(
        None,
        ge=0,
        le=1,
        description="Teto do aporte para o PISO da reserva (0..1). 1 = prioridade absoluta "
        "(padrão). Com o piso já composto não há déficit e o teto não faz nada.",
    )

    @field_validator("reserve_floor_date")
    @classmethod
    def _data_base_valida(cls, v: Optional[str]) -> Optional[str]:
        """Data-base solta corromperia a correção em silêncio — a mesma disciplina dos
        lançamentos da renda fixa."""
        if v is None or not str(v).strip():
            return None
        try:
            d = date.fromisoformat(str(v)[:10])
        except ValueError as exc:
            raise ValueError("Data-base inválida — use o formato aaaa-mm-dd.") from exc
        if d > date.today():
            raise ValueError(f"Data-base no futuro ({d.isoformat()}) — o piso parte do passado.")
        if d.year < 1994:  # Plano Real; antes disso é typo
            raise ValueError(f"Ano {d.year} parece um erro de digitação.")
        return d.isoformat()

    @field_validator("dimension_targets")
    @classmethod
    def _dimension_targets_validos(
        cls, v: Optional[Dict[str, Dict[str, float]]]
    ) -> Optional[Dict[str, Dict[str, float]]]:
        """Metas de visualização. `bucket` não entra aqui: a dimensão que dirige a compra é
        `targets` + `class_targets`, e aceitar uma segunda meta vinculante criaria um
        sistema sobredeterminado sem solução para a maioria das combinações.

        A soma pode ficar ABAIXO de 100%: "quero 20% internacional" é uma meta completa
        para quem não quer opinar sobre o resto. Acima de 100% é impossível, e aí é erro.
        """
        if v is None:
            return None
        permitidas = tuple(d for d in DIMENSIONS if d != "bucket")
        out: Dict[str, Dict[str, float]] = {}
        for raw_dim, weights in v.items():
            d = (raw_dim or "").strip().lower()
            if d not in permitidas:
                raise ValueError(
                    f"dimensão '{raw_dim}' não aceita meta; use {', '.join(permitidas)}."
                )
            if not weights:
                continue  # metas removidas
            norm = {c.strip().upper(): float(w) for c, w in weights.items()}
            if any(w <= 0 for w in norm.values()):
                raise ValueError(f"metas de {d} devem ser > 0.")
            total = sum(norm.values())
            if total > 1.0 + 0.001:
                raise ValueError(f"metas de {d} somam {total * 100:.1f}% — mais que a carteira.")
            out[d] = norm
        return out

    @field_validator("class_targets")
    @classmethod
    def _class_targets_validos(
        cls, v: Optional[Dict[str, Dict[str, float]]]
    ) -> Optional[Dict[str, Dict[str, float]]]:
        """Carteira alvo por classe: {"FII": {"AAA11": 0.4, ...}}. Pesos somam 1 por classe;
        classe com dict vazio remove a cesta daquela classe.

        Os itens de `RENDA_FIXA` são TAGS DE INDEXADOR (CDI, IPCA, LCI…) e não tickers —
        mesma aritmética, outro tipo de item. A existência da tag não é validada aqui: uma
        tag com peso e nenhuma conta é um estado legítimo (alvo definido, ainda não
        aplicado), e a tela o mostra como déficit em vez de recusar o salvamento.
        """
        if v is None:
            return None
        out: Dict[str, Dict[str, float]] = {}
        for raw_cls, weights in v.items():
            c = raw_cls.strip().upper()
            if c not in ALLOCATION_CLASSES:
                raise ValueError(
                    f"classe '{raw_cls}' inválida na carteira alvo; use {', '.join(ALLOCATION_CLASSES)}."
                )
            if not weights:
                continue  # cesta removida
            norm = {t.strip().upper(): float(w) for t, w in weights.items()}
            if any(w <= 0 for w in norm.values()):
                raise ValueError(f"pesos da carteira alvo de {c} devem ser > 0.")
            total = sum(norm.values())
            if abs(total - 1.0) > 0.001:
                raise ValueError(
                    f"pesos da carteira alvo de {c} somam {total * 100:.1f}%, deveriam somar 100%."
                )
            out[c] = norm
        return out


@router.get("/preferences")
async def get_preferences() -> dict:
    # A carteira alvo é a primeira coisa que a interface carrega: é aqui que a conversão
    # única do mecanismo aposentado acontece, e não num read que grava por dentro.
    db, settings = get_db(), get_settings()
    await preferences_repo.seed_renda_fixa_from_reserve_target(db, settings)
    return await preferences_repo.get(db, settings)


@router.put("/preferences")
async def put_preferences(body: PreferencesBody) -> dict:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return await preferences_repo.put(get_db(), patch, get_settings())
