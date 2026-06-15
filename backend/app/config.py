"""Configuração via variáveis de ambiente (lidas do `.env` no deploy)."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Ghostfolio (somente leitura)
    ghostfolio_url: str = Field("http://host.docker.internal:3333", alias="GHOSTFOLIO_URL")
    ghostfolio_access_token: str = Field("", alias="GHOSTFOLIO_ACCESS_TOKEN")

    # brapi.dev
    brapi_token: str = Field("", alias="BRAPI_TOKEN")
    brapi_base_url: str = Field("https://brapi.dev/api", alias="BRAPI_BASE_URL")

    # Cache
    redis_url: str = Field("", alias="REDIS_URL")

    # Servidor
    cors_origins: str = Field("*", alias="CORS_ORIGINS")

    # Alvos default de alocação por classe (somam 1.0)
    default_targets: dict = Field(
        default_factory=lambda: {"STOCK": 0.50, "FII": 0.30, "ETF": 0.15, "BDR": 0.05}
    )
    # Pesos default das 4 famílias de métricas (somam 1.0) — preset "Equilibrado"
    default_weights: dict = Field(
        default_factory=lambda: {
            "valuation": 0.30,  # desconto / Graham (P/VP, P/L, P/L×P/VP)
            "dividend": 0.35,  # Bazin (preço-teto) + consistência + yield
            "rebalance": 0.20,  # gap vs alvos da carteira
            "sector": 0.15,  # afinidade com setores perenes (Barsi BESST)
        }
    )

    @property
    def cors_list(self) -> List[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Presets de estratégia: só mudam os PESOS das famílias de métricas (transparente).
STRATEGY_PRESETS: dict = {
    "equilibrado": {
        "label": "Equilibrado",
        "description": "Mistura desconto, dividendos, rebalanceamento e setores perenes.",
        "weights": {"valuation": 0.30, "dividend": 0.35, "rebalance": 0.20, "sector": 0.15},
    },
    "barsi": {
        "label": "Barsi (dividendos perenes)",
        "description": "Foco em pagadoras consistentes de setores essenciais (BESST), buy & hold.",
        "weights": {"valuation": 0.20, "dividend": 0.40, "rebalance": 0.15, "sector": 0.25},
    },
    "bazin": {
        "label": "Bazin (preço-teto)",
        "description": "Comprar com margem sobre o preço-teto (DY-alvo de 6%) e dividendos recorrentes.",
        "weights": {"valuation": 0.25, "dividend": 0.50, "rebalance": 0.20, "sector": 0.05},
    },
    "graham": {
        "label": "Graham (valor)",
        "description": "Margem de segurança no preço: P/VP e P/L baixos, P/L×P/VP ≤ 22,5.",
        "weights": {"valuation": 0.55, "dividend": 0.20, "rebalance": 0.25, "sector": 0.00},
    },
}

# Palavras-chave dos setores perenes do método BESST de Luiz Barsi (Bancos, Energia,
# Saneamento, Seguros, Telecomunicações). Casamento por substring, em PT e EN, já que a
# brapi costuma devolver o setor em inglês.
BESST_KEYWORDS: tuple = (
    "banco", "bank", "financ",  # Bancos / financeiro
    "energia", "energy", "electric", "utilities", "utilit",  # Energia
    "saneament", "água", "water",  # Saneamento
    "seguro", "insurance",  # Seguros
    "telecom",  # Telecomunicações
)
