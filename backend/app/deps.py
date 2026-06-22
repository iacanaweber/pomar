"""Injeção de dependências — instâncias compartilhadas (cache e clientes)."""
from __future__ import annotations

from functools import lru_cache

from app.cache.store import Cache
from app.clients.brapi import BrapiClient
from app.clients.ghostfolio import GhostfolioClient
from app.config import get_settings
from app.repositories.db import Database


@lru_cache
def get_db() -> Database:
    return Database(get_settings().db_path)


@lru_cache
def get_cache() -> Cache:
    return Cache(get_settings().redis_url)


@lru_cache
def get_ghostfolio() -> GhostfolioClient:
    s = get_settings()
    return GhostfolioClient(s.ghostfolio_url, s.ghostfolio_access_token)


@lru_cache
def get_brapi() -> BrapiClient:
    s = get_settings()
    return BrapiClient(s.brapi_base_url, s.brapi_token, get_cache(), batch_size=s.brapi_batch)
