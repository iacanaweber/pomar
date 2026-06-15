"""Rotas de saúde, glossário e estratégias."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import STRATEGY_PRESETS, get_settings
from app.data.glossary import get_glossary
from app.deps import get_brapi, get_ghostfolio

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    gf = await get_ghostfolio().health()
    br = await get_brapi().health()
    return {"status": "ok", "ghostfolio": gf, "brapi": br}


@router.get("/glossary")
async def glossary() -> dict:
    return get_glossary()


@router.get("/debug/brapi")
async def debug_brapi(ticker: str = "BBAS3") -> dict:
    """Diagnóstico da conexão com a brapi (status HTTP, token presente, resposta crua).

    NÃO expõe o token — só o tamanho. Útil para descobrir por que um ticker falha.
    """
    return await get_brapi().diagnose(ticker)


@router.get("/strategies")
async def strategies() -> dict:
    return {
        "presets": STRATEGY_PRESETS,
        "default_targets": get_settings().default_targets,
    }
