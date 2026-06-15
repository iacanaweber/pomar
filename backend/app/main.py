"""Pomar — API. Plante seus aportes, colha dividendos. 🌳

App de planejamento de aportes na B3: lê a carteira do Ghostfolio (somente leitura),
busca dados de mercado na brapi e recomenda compras com base em estratégias consagradas
(Barsi, Bazin, Graham) — sempre de forma transparente e explicável.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_market, routes_meta, routes_plan, routes_portfolio
from app.config import get_settings

app = FastAPI(
    title="Pomar",
    description="Plante seus aportes, colha dividendos. Recomendações transparentes para a B3.",
    version="0.1.0",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_meta.router, prefix="/api", tags=["meta"])
app.include_router(routes_portfolio.router, prefix="/api", tags=["portfolio"])
app.include_router(routes_market.router, prefix="/api", tags=["market"])
app.include_router(routes_plan.router, prefix="/api", tags=["plan"])


@app.get("/api")
async def root() -> dict:
    return {"app": "Pomar", "tagline": "Plante seus aportes, colha dividendos.", "docs": "/docs"}
