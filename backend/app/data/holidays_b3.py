"""Feriados da B3 (dias sem pregão) — para contar dias úteis no rendimento da renda fixa.

GERADOS POR ALGORITMO (não mais curados à mão): os feriados móveis (Carnaval, Sexta-feira
Santa, Corpus Christi) derivam da Páscoa pelo cálculo de Gauss; os fixos valem todo ano.
Isso elimina a bomba-relógio da lista curada, que expirava em 2027 e degradava a contagem
silenciosamente. A geração cobre 1994–2100 (frozenset pré-computado; ~1,4 mil datas).

Regras da B3: sem pregão em Confraternização (1/1), Carnaval (seg+ter), Sexta-feira Santa,
Tiradentes (21/4), Dia do Trabalho (1/5), Corpus Christi, Independência (7/9), N. Sra.
Aparecida (12/10), Finados (2/11), Proclamação da República (15/11), Consciência Negra
(20/11, feriado nacional desde 2024), véspera de Natal (24/12), Natal (25/12) e último dia
do ano (31/12). Feriados em fim de semana são inofensivos (a contagem já exclui sáb/dom).
"""
from __future__ import annotations

from datetime import date, timedelta

_YEARS = range(1994, 2101)  # Plano Real em diante; folga generosa para o futuro


def easter_sunday(year: int) -> date:
    """Domingo de Páscoa pelo algoritmo de Gauss (calendário gregoriano)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 19 * l) // 433
    month = (h + l - 7 * m + 90) // 25
    day = (h + l - 7 * m + 33 * month + 19) % 32
    return date(year, month, day)


def b3_holidays_for_year(year: int) -> set[date]:
    easter = easter_sunday(year)
    holidays = {
        date(year, 1, 1),                   # Confraternização Universal
        easter - timedelta(days=48),        # Carnaval (segunda)
        easter - timedelta(days=47),        # Carnaval (terça)
        easter - timedelta(days=2),         # Sexta-feira Santa
        date(year, 4, 21),                  # Tiradentes
        date(year, 5, 1),                   # Dia do Trabalho
        easter + timedelta(days=60),        # Corpus Christi
        date(year, 9, 7),                   # Independência
        date(year, 10, 12),                 # N. Sra. Aparecida
        date(year, 11, 2),                  # Finados
        date(year, 11, 15),                 # Proclamação da República
        date(year, 12, 24),                 # véspera de Natal (B3 fechada)
        date(year, 12, 25),                 # Natal
        date(year, 12, 31),                 # último dia do ano (B3 fechada)
    }
    if year >= 2024:                        # Consciência Negra: feriado nacional desde 2024
        holidays.add(date(year, 11, 20))
    return holidays


B3_HOLIDAYS: frozenset[date] = frozenset(
    d for y in _YEARS for d in b3_holidays_for_year(y)
)
