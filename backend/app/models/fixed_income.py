"""Modelos da renda fixa (rastreador manual de contas + lançamentos)."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

_TZ_BR = ZoneInfo("America/Sao_Paulo")


class AccountIn(BaseModel):
    name: str = Field(..., description="Ex.: 'CDB Banco X', 'Tesouro Selic 2029', 'Conta'.")
    institution: Optional[str] = None
    kind: Optional[str] = Field(None, description="'cdb'|'tesouro'|'poupanca'|'conta'|'outro'.")
    benchmark: Optional[str] = Field(None, description="'cdi'|'selic'|'prefixado'|'ipca' (informativo).")


class AccountPatch(BaseModel):
    """PATCH parcial da conta: só os campos enviados mudam. `archived=False` desarquiva —
    arquivar deixou de ser sem-volta na UI."""

    name: Optional[str] = None
    institution: Optional[str] = None
    kind: Optional[str] = None
    benchmark: Optional[str] = None
    archived: Optional[bool] = None


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
    current_balance: float = 0.0
    # Rendimento da última atualização de saldo (vs a anterior), anualizado base 252.
    last_yield_annual: Optional[float] = Field(None, description="Rendimento anualizado (fração).")
    last_yield_gain: Optional[float] = Field(None, description="Ganho do período (BRL).")
    last_yield_from: Optional[str] = None
    last_yield_to: Optional[str] = None
    last_yield_business_days: Optional[int] = None
    pct_of_cdi: Optional[float] = Field(None, description="Rendimento como fração do CDI (1.0 = 100%).")


class FixedIncomeSummary(BaseModel):
    accounts: List[AccountSummary] = Field(default_factory=list)
    total_balance: float = 0.0
    cdi_annual: Optional[float] = Field(None, description="CDI anualizado (fração), benchmark.")
    currency: str = "BRL"
