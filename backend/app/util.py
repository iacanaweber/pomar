"""Utilidades pequenas e compartilhadas."""
from __future__ import annotations


def normalize_ticker(ticker: str) -> str:
    """Normaliza um símbolo da B3 para o formato da brapi.

    O Ghostfolio (padrão Yahoo) usa sufixo de bolsa, ex: 'BBAS3.SA'. A brapi espera
    o código puro: 'BBAS3'. Também remove espaços e padroniza maiúsculas.
    """
    t = (ticker or "").strip().upper()
    if t.endswith(".SA"):
        t = t[:-3]
    return t
