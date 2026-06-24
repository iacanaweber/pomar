"""Rotas de preferências do usuário (persistidas em SQLite)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.deps import get_db
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


@router.get("/preferences")
async def get_preferences() -> dict:
    return await preferences_repo.get(get_db(), get_settings())


@router.put("/preferences")
async def put_preferences(body: PreferencesBody) -> dict:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return await preferences_repo.put(get_db(), patch, get_settings())
