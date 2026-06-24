"""Modelos da renda fixa (rastreador manual de contas + lançamentos)."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AccountIn(BaseModel):
    name: str = Field(..., description="Ex.: 'CDB Banco X', 'Tesouro Selic 2029', 'Conta'.")
    institution: Optional[str] = None
    kind: Optional[str] = Field(None, description="'cdb'|'tesouro'|'poupanca'|'conta'|'outro'.")
    benchmark: Optional[str] = Field(None, description="'cdi'|'selic'|'prefixado'|'ipca' (informativo).")


class EntryIn(BaseModel):
    kind: Literal["balance", "deposit", "withdrawal"] = Field(
        ..., description="balance = atualização de saldo; deposit = aporte; withdrawal = resgate."
    )
    amount: float = Field(..., gt=0, description="Saldo observado (balance) ou valor (deposit/withdrawal).")
    entry_date: Optional[str] = Field(None, description="Data ISO yyyy-mm-dd (padrão: hoje).")
    note: Optional[str] = None


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
