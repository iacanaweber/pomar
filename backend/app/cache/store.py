"""Cache com TTL. Usa Redis se REDIS_URL estiver setado; senão, cache em memória.

Guarda também a entrada "stale" (sem expirar de fato) para servir dado defasado
quando a brapi falhar — marcando a proveniência como `stale=True`.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional, Tuple


class Cache:
    def __init__(self, redis_url: str = "") -> None:
        self._redis = None
        self._mem: dict[str, Tuple[float, Any]] = {}  # key -> (expires_at, value)
        if redis_url:
            try:
                import redis  # type: ignore

                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                # Redis indisponível: degrada silenciosamente para memória.
                self._redis = None

    def get(self, key: str) -> Optional[Any]:
        """Retorna o valor se ainda válido (não expirado), senão None."""
        if self._redis is not None:
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        item = self._mem.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at and expires_at < time.time():
            return None
        return value

    def get_stale(self, key: str) -> Optional[Any]:
        """Retorna o último valor conhecido mesmo que expirado (fallback)."""
        if self._redis is not None:
            raw = self._redis.get(f"stale:{key}")
            return json.loads(raw) if raw else None
        item = self._mem.get(key)
        return item[1] if item else None

    def set(self, key: str, value: Any, ttl: int) -> None:
        if self._redis is not None:
            payload = json.dumps(value)
            self._redis.set(key, payload, ex=ttl)
            # cópia "stale" com validade longa para fallback
            self._redis.set(f"stale:{key}", payload, ex=max(ttl * 10, 86400))
            return
        self._mem[key] = (time.time() + ttl, value)
