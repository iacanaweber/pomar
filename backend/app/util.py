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


def to_cents(value: float | int | None) -> int:
    """Reais -> centavos inteiros, para somar dinheiro sem acumular erro de ponto flutuante.

    O backend usa `float` na cadeia monetária inteira por herança; código novo que SOMA
    valores acumula em centavos e volta para float só na borda (`from_cents`). Somar
    milhares de saldos em float faz o total derivar do que a soma dos números exibidos diz.
    """
    return int(round(float(value or 0.0) * 100))


def from_cents(cents: int) -> float:
    """Centavos inteiros -> reais, arredondado a 2 casas (a borda do Pydantic)."""
    return round(cents / 100.0, 2)
