"""Rotas de preferências do usuário (persistidas em SQLite)."""
from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from app.config import get_settings
from app.deps import get_db
from app.models.scoring import INVESTABLE_CLASSES, validate_focus
from app.repositories import preferences_repo

router = APIRouter()


class PreferencesBody(BaseModel):
    """Campos opcionais — só os enviados são atualizados (patch)."""

    strategy: Optional[str] = None
    aporte_default: Optional[float] = None
    targets: Optional[dict] = None
    weights: Optional[dict] = None
    max_assets: Optional[int] = None
    max_weight_per_asset: Optional[float] = None
    min_ticket: Optional[float] = None
    lot_mode: Optional[str] = None
    reserve_target: Optional[float] = None
    bazin_target_mode: Optional[str] = None
    bazin_target_yield: Optional[float] = None
    target_monthly_income: Optional[float] = None
    target_horizon_years: Optional[int] = None
    annual_growth: Optional[float] = None
    expected_inflation: Optional[float] = None
    include_reserve_income: Optional[bool] = None
    focus: Optional[str] = None
    class_targets: Optional[Dict[str, Dict[str, float]]] = None

    @field_validator("focus")
    @classmethod
    def _focus_valido(cls, v: Optional[str]) -> Optional[str]:
        return validate_focus(v)

    @field_validator("class_targets")
    @classmethod
    def _class_targets_validos(
        cls, v: Optional[Dict[str, Dict[str, float]]]
    ) -> Optional[Dict[str, Dict[str, float]]]:
        """Carteira alvo por classe: {"FII": {"BTGL11": 0.4, ...}}. Pesos somam 1 por classe;
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
    return await preferences_repo.get(get_db(), get_settings())


@router.put("/preferences")
async def put_preferences(body: PreferencesBody) -> dict:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return await preferences_repo.put(get_db(), patch, get_settings())
