"""Modelos da renda fixa (rastreador manual de contas + lançamentos)."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.fixed_income import EARMARKED_NA_CARTEIRA as _EARMARKED_NA_CARTEIRA

_TZ_BR = ZoneInfo("America/Sao_Paulo")

# Para que serve o dinheiro. `earmarked` tem destino definido (a conta que provisiona o IR
# do ano seguinte) e NUNCA entra na carteira, mesmo marcada — não é patrimônio investível.
Purpose = Literal["investment", "earmarked"]

# Em quanto tempo o dinheiro está na mão. Só `immediate` satisfaz o piso da reserva: uma LCI
# com carência de dois anos soma no peso da classe, mas não serve de emergência.
Liquidity = Literal["immediate", "scheduled", "locked", "unknown"]

# `unknown` existe só para as contas que já estavam no banco antes da v7. Conta nova não
# nasce sem resposta: o tipo é o que torna o campo obrigatório no cadastro.
NewLiquidity = Literal["immediate", "scheduled", "locked"]


class AccountIn(BaseModel):
    name: str = Field(..., description="Ex.: 'CDB Banco X', 'Tesouro Selic 2029', 'Conta'.")
    institution: Optional[str] = None
    kind: Optional[str] = Field(None, description="'cdb'|'tesouro'|'poupanca'|'conta'|'outro'.")
    benchmark: Optional[str] = Field(None, description="'cdi'|'selic'|'prefixado'|'ipca' (informativo).")
    counts_in_portfolio: bool = Field(
        False, description="Entra no patrimônio, nos gráficos e no cálculo de alvos."
    )
    purpose: Purpose = "investment"
    liquidity: NewLiquidity = Field(
        ...,
        description="'immediate' (D+0/D+1) | 'scheduled' (janela/vencimento) | 'locked' (carência).",
    )
    redeem_days: Optional[int] = Field(
        None, ge=0, description="Dias até o resgate cair na conta (informativo)."
    )

    @model_validator(mode="after")
    def _earmarked_fora_da_carteira(self) -> "AccountIn":
        if self.purpose == "earmarked" and self.counts_in_portfolio:
            raise ValueError(_EARMARKED_NA_CARTEIRA)
        return self


class AccountPatch(BaseModel):
    """PATCH parcial da conta: só os campos enviados mudam. `archived=False` desarquiva —
    arquivar deixou de ser sem-volta na UI.

    A combinação proibida (`earmarked` + contar na carteira) é validada contra o estado
    MESCLADO, no repositório: aqui só se enxerga metade do par.
    """

    name: Optional[str] = None
    institution: Optional[str] = None
    kind: Optional[str] = None
    benchmark: Optional[str] = None
    archived: Optional[bool] = None
    counts_in_portfolio: Optional[bool] = None
    purpose: Optional[Purpose] = None
    liquidity: Optional[Liquidity] = None
    redeem_days: Optional[int] = Field(None, ge=0)


class EntryIn(BaseModel):
    kind: Literal["balance", "deposit", "withdrawal"] = Field(
        ..., description="balance = atualização de saldo; deposit = aporte; withdrawal = resgate."
    )
    amount: float = Field(..., gt=0, description="Saldo observado (balance) ou valor (deposit/withdrawal).")
    entry_date: Optional[str] = Field(None, description="Data ISO yyyy-mm-dd (padrão: hoje, Brasil).")
    note: Optional[str] = None

    @field_validator("entry_date")
    @classmethod
    def _check_entry_date(cls, v: Optional[str]) -> Optional[str]:
        """Data era string livre: um typo ('2062') entrava no SQLite e corrompia a taxa
        anualizada em silêncio. Valida formato, bloqueia futuro e ano absurdo."""
        if v is None:
            return v
        try:
            d = date.fromisoformat(str(v)[:10])
        except ValueError as exc:
            raise ValueError("Data inválida — use o formato aaaa-mm-dd.") from exc
        today_br = datetime.now(_TZ_BR).date()
        if d > today_br:
            raise ValueError(f"Data no futuro ({d.isoformat()}) — lançamentos registram o passado.")
        if d.year < 1994:  # Plano Real; antes disso é typo
            raise ValueError(f"Ano {d.year} parece um erro de digitação.")
        return d.isoformat()


class EntryOut(BaseModel):
    id: int
    account_id: int
    kind: str
    amount: float
    entry_date: str
    note: Optional[str] = None


class AccountSummary(BaseModel):
    id: int
    name: str
    institution: Optional[str] = None
    kind: Optional[str] = None
    benchmark: Optional[str] = None
    archived: bool = False
    counts_in_portfolio: bool = False
    purpose: Purpose = "investment"
    liquidity: Liquidity = "unknown"
    redeem_days: Optional[int] = None
    # Derivado: marcada E de propósito 'investment'. É o que a Carteira soma.
    in_portfolio: bool = Field(
        False, description="Efetivamente contabilizada no patrimônio (marcada e não earmarked)."
    )
    current_balance: float = 0.0
    # Rendimento de TODO o histórico (retorno tempo-ponderado, base 252) — é o número da tela.
    history_yield_annual: Optional[float] = Field(None, description="Rendimento anualizado (fração).")
    history_yield_gain: Optional[float] = Field(None, description="Ganho acumulado no histórico (BRL).")
    history_yield_from: Optional[str] = None
    history_yield_to: Optional[str] = None
    history_yield_business_days: Optional[int] = None
    # Última atualização de saldo (vs a anterior) — diagnóstico: janela curta, taxa instável.
    last_yield_annual: Optional[float] = Field(None, description="Rendimento anualizado (fração).")
    last_yield_gain: Optional[float] = Field(None, description="Ganho do período (BRL).")
    last_yield_from: Optional[str] = None
    last_yield_to: Optional[str] = None
    last_yield_business_days: Optional[int] = None
    pct_of_cdi: Optional[float] = Field(None, description="Rendimento do histórico como fração do CDI (1.0 = 100%).")


class FixedIncomeSummary(BaseModel):
    accounts: List[AccountSummary] = Field(default_factory=list)
    total_balance: float = Field(0.0, description="Tudo que existe na aba Reserva (contas ativas).")
    portfolio_balance: float = Field(
        0.0, description="Parte que conta na carteira (marcada e com propósito 'investment')."
    )
    liquid_balance: float = Field(
        0.0,
        description="Reserva LÍQUIDA: da parte que conta na carteira, só o que tem resgate "
        "imediato. É o que satisfaz o piso da reserva.",
    )
    excluded_balance: float = Field(
        0.0, description="Saldo que não conta na carteira (não marcado ou earmarked)."
    )
    cdi_annual: Optional[float] = Field(None, description="CDI anualizado (fração), benchmark.")
    currency: str = "BRL"
