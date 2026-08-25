"""Rotas de saúde, glossário e diagnóstico."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
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

    NÃO expõe o token — só o tamanho. Disponível apenas com DEBUG=true (404 caso contrário),
    para não vazar configuração em produção.
    """
    if not get_settings().debug:
        raise HTTPException(status_code=404, detail="Não encontrado")
    return await get_brapi().diagnose(ticker)
