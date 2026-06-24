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
METRIC_FAMILIES = {"valuation", "dividend", "rebalance", "sector"}


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

    # Alvos default de alocação por classe (somam 1.0). Renda fixa entra na Fase 1,
    # junto com o alocador que sabe tratá-la — por isso ainda não está aqui.
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

    @field_validator("default_weights")
    @classmethod
    def _check_weights(cls, v: dict) -> dict:
        return _validate_weight_map(v, METRIC_FAMILIES, "default_weights")

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
        "description": "Margem de segurança no preço: P/VP e P/L baixos, P/L×P/VP ≤ 22,5, "
        "lucro positivo. Exclui empresas fora desses critérios.",
        "weights": {"valuation": 0.55, "dividend": 0.20, "rebalance": 0.25, "sector": 0.00},
    },
    "dividend_growth": {
        "label": "Dividend Growth",
        "description": "Prioriza crescimento e consistência de proventos em pagadoras recorrentes.",
        "weights": {"valuation": 0.15, "dividend": 0.45, "rebalance": 0.15, "sector": 0.25},
    },
    "valor_qualidade": {
        "label": "Valor + Qualidade",
        "description": "Desconto (valuation) com empresas de qualidade — o eixo de risco "
        "penaliza dívida alta, payout insustentável e prejuízo.",
        "weights": {"valuation": 0.45, "dividend": 0.20, "rebalance": 0.20, "sector": 0.15},
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

# Afinidade GRADUADA com os setores perenes de Barsi (BESST), em [0,1]. Substitui o flag
# binário por substring: bancos/energia/saneamento/seguros/telecom = 1.0; "serviços
# financeiros"/corretora/fintech = 0.3 (Barsi reserva o 1.0 a BANCOS, não a qualquer
# financeira). O matching é por substring (case-insensitive) e retorna a MAIOR afinidade
# casada. Setor presente mas sem casar => 0.0; setor ausente => indisponível.
SECTOR_AFFINITY_MAP: dict = {
    # Bancos
    "banco": 1.0, "bank": 1.0,
    # Energia
    "energia elétrica": 1.0, "energia eletrica": 1.0, "energia": 1.0,
    "energy": 1.0, "electric": 1.0, "utilities": 1.0,
    "utilidade pública": 0.8, "utilidade publica": 0.8,
    # Saneamento
    "saneament": 1.0, "água": 1.0, "agua": 1.0, "water": 1.0,
    # Seguros / previdência
    "seguro": 1.0, "seguros": 1.0, "insurance": 1.0,
    "previdência": 0.8, "previdencia": 0.8,
    # Telecom
    "telecom": 1.0, "telecomunicaç": 1.0,
    # Financeiro amplo (NÃO é banco): corretora/fintech/serviços financeiros
    "serviços financeiros": 0.3, "servicos financeiros": 0.3, "financ": 0.3,
    "corretora": 0.3, "fintech": 0.3,
}
