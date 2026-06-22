"""Pomar — API. Plante seus aportes, colha dividendos. 🌳

App de planejamento de aportes na B3: lê a carteira do Ghostfolio (somente leitura),
busca dados de mercado (Fundamentus + StatusInvest + brapi) e recomenda compras com base
em estratégias consagradas (Barsi, Bazin, Graham) — sempre de forma transparente.

v2: app montado por factory (`create_app`), autenticação por senha única, docs/diagnóstico
expostos só em DEBUG, e CORS restrito (mesma origem por padrão).
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_income,
    routes_market,
    routes_meta,
    routes_plan,
    routes_portfolio,
    routes_preferences,
    routes_watchlist,
)
from app.api.security import AuthMiddleware
from app.api.security import router as auth_router
from app.config import Settings, get_settings

log = logging.getLogger("pomar")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pré-aquece o cache do universo no boot, para o primeiro plano não estourar timeout."""

    async def warm() -> None:
        try:
            from app.data.watchlist import default_universe
            from app.deps import get_brapi, get_cache
            from app.services import market_data

            await market_data.build_assets(default_universe(), get_cache(), get_brapi())
            log.info("warmup do universo concluído")
        except Exception as exc:  # noqa: BLE001
            log.warning("warmup do universo falhou: %r", exc)

    app.state.warmup_task = asyncio.create_task(warm())
    yield
    # shutdown: fecha a conexão do SQLite, se aberta
    try:
        from app.deps import get_db

        await get_db().close()
    except Exception as exc:  # noqa: BLE001
        log.warning("falha ao fechar o banco no shutdown: %r", exc)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Pomar",
        description="Plante seus aportes, colha dividendos. Recomendações transparentes para a B3.",
        version="2.0.0",
        lifespan=lifespan,
        # Documentação interativa e schema só em DEBUG (não vazar o mapa da API em produção).
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    # Auth primeiro (interno); CORS por fora, para tratar preflight antes da auth.
    app.add_middleware(AuthMiddleware)
    if settings.cors_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Content-Type"],
        )

    app.include_router(auth_router, prefix="/api", tags=["auth"])
    app.include_router(routes_meta.router, prefix="/api", tags=["meta"])
    app.include_router(routes_portfolio.router, prefix="/api", tags=["portfolio"])
    app.include_router(routes_market.router, prefix="/api", tags=["market"])
    app.include_router(routes_plan.router, prefix="/api", tags=["plan"])
    app.include_router(routes_preferences.router, prefix="/api", tags=["preferences"])
    app.include_router(routes_watchlist.router, prefix="/api", tags=["watchlist"])
    app.include_router(routes_income.router, prefix="/api", tags=["income"])

    @app.get("/api")
    async def root() -> dict:
        return {"app": "Pomar", "tagline": "Plante seus aportes, colha dividendos.", "version": "2.0.0"}

    return app


app = create_app()
