"""Configuração via variáveis de ambiente (lidas do `.env` no deploy).

v2: validação explícita (alvos/pesos somam 1.0, chaves conhecidas), parâmetros de
segurança (senha única, DEBUG, CORS sem default permissivo) e persistência (SQLite).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Conjuntos canônicos usados para validar a configuração (Enums de domínio chegam no
# lift-and-shift da Fase 1; aqui validamos as chaves contra estes conjuntos).
ASSET_CLASSES = {"STOCK", "FII", "ETF", "BDR", "FIXED_INCOME"}


def _validate_weight_map(value: Dict[str, float], allowed: set, label: str) -> Dict[str, float]:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{label}: chaves desconhecidas {sorted(unknown)} (permitidas: {sorted(allowed)})")
    total = sum(value.values())
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"{label}: a soma deve ser 1.0 (soma atual = {total:.3f})")
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True
    )

    # Ghostfolio (somente leitura)
    ghostfolio_url: str = Field("http://host.docker.internal:3333", alias="GHOSTFOLIO_URL")
    ghostfolio_access_token: str = Field("", alias="GHOSTFOLIO_ACCESS_TOKEN")

    # brapi.dev
    brapi_token: str = Field("", alias="BRAPI_TOKEN")
    brapi_base_url: str = Field("https://brapi.dev/api", alias="BRAPI_BASE_URL")
    # Tickers por requisição. O plano GRÁTIS da brapi aceita só 1 por chamada
    # (multi-ticker é recurso PRO). Aumente se você tiver um plano pago.
    brapi_batch: int = Field(1, alias="BRAPI_BATCH")
    # Capacidade do plano, explícita (substitui a sondagem em runtime na Fase 1).
    brapi_plan: str = Field("free", alias="BRAPI_PLAN")  # "free" | "pro"

    # Cache
    redis_url: str = Field("", alias="REDIS_URL")

    # Segurança / servidor
    app_password: str = Field("", alias="APP_PASSWORD")  # senha única; vazio => API bloqueada
    debug: bool = Field(False, alias="DEBUG")  # expõe /docs e /api/debug/* só quando True
    cors_origins: str = Field("", alias="CORS_ORIGINS")  # vazio => apenas mesma origem
    session_ttl_hours: int = Field(720, alias="SESSION_TTL_HOURS")  # 30 dias
    # Cookie de sessão Secure (só trafega em HTTPS). Padrão False para funcionar em HTTP/LAN;
    # ATIVE (true) ao servir por HTTPS (ex.: atrás do Caddy/TLS). Em HTTP, true quebra o login.
    cookie_secure: bool = Field(False, alias="COOKIE_SECURE")

    # Persistência (SQLite, single-user)
    db_path: str = Field("data/pomar.db", alias="DB_PATH")
    # Backup automático do SQLite: snapshot diário via API de backup, com retenção.
    # Fica DENTRO do volume de dados (data/backups) — protege contra corrupção e erro
    # de migração; para desastre de disco, copie o volume para fora periodicamente.
    backup_enabled: bool = Field(True, alias="BACKUP_ENABLED")
    backup_dir: str = Field("data/backups", alias="BACKUP_DIR")
    backup_retention: int = Field(14, alias="BACKUP_RETENTION")

    # Alvos default de alocação por classe (somam 1.0) — ponto de partida que o usuário
    # ajusta na Carteira alvo. A reserva/renda fixa é tratada à parte (services/reserve).
    default_targets: dict = Field(
        default_factory=lambda: {"STOCK": 0.50, "FII": 0.30, "ETF": 0.15, "BDR": 0.05}
    )

    @field_validator("brapi_plan")
    @classmethod
    def _check_plan(cls, v: str) -> str:
        v = (v or "free").strip().lower()
        if v not in {"free", "pro"}:
            raise ValueError("BRAPI_PLAN deve ser 'free' ou 'pro'")
        return v

    @field_validator("default_targets")
    @classmethod
    def _check_targets(cls, v: dict) -> dict:
        return _validate_weight_map(v, ASSET_CLASSES, "default_targets")

    @property
    def cors_list(self) -> List[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
