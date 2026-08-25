"""Utilidades pequenas e compartilhadas."""
from __future__ import annotations

import re

# Forma de um símbolo da B3: 4 caracteres (o primeiro é letra) + 1 ou 2 dígitos + sufixo
# opcional de fracionário. O segundo caractere aceita dígito por causa de B5P211.
_TICKER_SHAPE = re.compile(r"^[A-Z][A-Z0-9]{3}[0-9]{1,2}[A-Z]?$")


def looks_like_ticker(code: str) -> bool:
    """O código é um TICKER da B3 (IMAB11) ou um código livre (CDI, IPCA_LONGO)?

    A cesta de renda fixa guarda os dois tipos de item lado a lado — a tag de indexador,
    que se cumpre lançando dinheiro numa conta, e o ticker, que se cumpre comprando cotas.
    Esta é a função que os separa.

    Regra SINTÁTICA, e não uma consulta ao banco: a pergunta "existe rótulo `indexer` com
    este código?" transformaria uma tag ainda não criada num ticker fantasma — o plano
    pediria cotação, falharia, e o item sumiria da cesta em silêncio. A forma não depende
    de estado e é a mesma nos dois lados do app.

    Os dois falsos positivos plausíveis (IPCA45, CDI110) são fechados na borda de escrita:
    `labels_repo.create_label` recusa código de indexador com forma de ticker.
    """
    return bool(_TICKER_SHAPE.match((code or "").strip().upper()))


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
