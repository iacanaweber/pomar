"""Feriados da B3 (dias sem pregão) — para contar dias úteis no rendimento da renda fixa.

Lista curada dos feriados nacionais e específicos da B3 (que não abre em 24/12 e 31/12).
Feriados que caem em fim de semana são inofensivos (já são excluídos pela contagem seg–sex).
Cobertura 2024–2027; fora dessa janela a contagem cai para seg–sex puro (aproximação — o
impacto de ±1 feriado sobre a taxa anualizada é < 1%). Atualize anualmente.
"""
from __future__ import annotations

from datetime import date

# (ano, mês, dia)
_RAW: tuple[tuple[int, int, int], ...] = (
    # 2024
    (2024, 1, 1), (2024, 2, 12), (2024, 2, 13), (2024, 3, 29), (2024, 4, 21),
    (2024, 5, 1), (2024, 5, 30), (2024, 9, 7), (2024, 10, 12), (2024, 11, 2),
    (2024, 11, 15), (2024, 11, 20), (2024, 12, 24), (2024, 12, 25), (2024, 12, 31),
    # 2025
    (2025, 1, 1), (2025, 3, 3), (2025, 3, 4), (2025, 4, 18), (2025, 4, 21),
    (2025, 5, 1), (2025, 6, 19), (2025, 9, 7), (2025, 10, 12), (2025, 11, 2),
    (2025, 11, 15), (2025, 11, 20), (2025, 12, 24), (2025, 12, 25), (2025, 12, 31),
    # 2026
    (2026, 1, 1), (2026, 2, 16), (2026, 2, 17), (2026, 4, 3), (2026, 4, 21),
    (2026, 5, 1), (2026, 6, 4), (2026, 9, 7), (2026, 10, 12), (2026, 11, 2),
    (2026, 11, 15), (2026, 11, 20), (2026, 12, 24), (2026, 12, 25), (2026, 12, 31),
    # 2027
    (2027, 1, 1), (2027, 2, 8), (2027, 2, 9), (2027, 3, 26), (2027, 4, 21),
    (2027, 5, 1), (2027, 5, 27), (2027, 9, 7), (2027, 10, 12), (2027, 11, 2),
    (2027, 11, 15), (2027, 11, 20), (2027, 12, 24), (2027, 12, 25), (2027, 12, 31),
)

B3_HOLIDAYS: frozenset[date] = frozenset(date(y, m, d) for (y, m, d) in _RAW)
