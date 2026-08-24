"""Rotas de preferências do usuário (persistidas em SQLite)."""
from __future__ import annotations

from datetime import date
from typing import Dict, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.deps import get_db
from app.models.plan import INVESTABLE_CLASSES
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
    legacy_in_total: Optional[bool] = Field(
        None,
        description="Se os ativos fora da carteira alvo entram no patrimônio que serve de "
        "base para os alvos em R$ das demais classes.",
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

    @field_validator("class_targets")
    @classmethod
    def _class_targets_validos(
        cls, v: Optional[Dict[str, Dict[str, float]]]
    ) -> Optional[Dict[str, Dict[str, float]]]:
        """Carteira alvo por classe: {"FII": {"AAA11": 0.4, ...}}. Pesos somam 1 por classe;
        classe com dict vazio remove a cesta daquela classe."""
        if v is None:
            return None
        out: Dict[str, Dict[str, float]] = {}
        for raw_cls, weights in v.items():
            c = raw_cls.strip().upper()
            if c not in INVESTABLE_CLASSES:
                raise ValueError(
                    f"classe '{raw_cls}' inválida na carteira alvo; use {', '.join(INVESTABLE_CLASSES)}."
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
