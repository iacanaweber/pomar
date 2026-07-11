"""Testes do provedor StatusInvest: tipo de provento, datas e DY trailing-365d."""
from __future__ import annotations

from datetime import date

from app.providers import statusinvest as si


def test_net_factor_by_type():
    assert si._net_factor("JCP") == 0.85
    assert si._net_factor("Juros Sobre Capital Próprio") == 0.85
    assert si._net_factor("Rend. Tributado") == 0.85
    assert si._net_factor("Dividendo") == 1.0
    assert si._net_factor("Rendimento") == 1.0  # FII isento p/ PF
    assert si._net_factor(None) == 1.0


def test_parse_date():
    assert si._parse_date("04/01/2027") == date(2027, 1, 4)
    assert si._parse_date("lixo") is None
    assert si._parse_date(None) is None


def test_trailing_365_gross_and_net():
    today = date(2026, 6, 24)
    payments = [
        {"pd": "01/06/2026", "v": 1.0, "et": "Dividendo"},  # dentro de 365d, isento
        {"pd": "01/06/2026", "v": 1.0, "et": "JCP"},         # dentro, JCP (×0,85)
        {"pd": "01/01/2024", "v": 5.0, "et": "Dividendo"},   # > 365d atrás: fora
        {"pd": "04/01/2027", "v": 9.0, "et": "JCP"},         # futuro: ignora
    ]
    assert si._trailing_365(payments, today, net=False) == 2.0
    assert abs(si._trailing_365(payments, today, net=True) - 1.85) < 1e-9  # 1.0 + 0.85


def test_amortizacao_e_subscricao_nao_contam_como_renda():
    """Amortização de FII é devolução de principal; subscrição é direito — nenhum dos
    dois é renda recorrente e não pode inflar DY, teto de Bazin nem calendário."""
    today = date(2026, 6, 24)
    payments = [
        {"pd": "01/06/2026", "v": 1.0, "et": "Rendimento"},
        {"pd": "01/05/2026", "v": 3.0, "et": "Amortização"},
        {"pd": "01/04/2026", "v": 2.0, "et": "Direito de Subscrição"},
    ]
    assert si._trailing_365(payments, today, net=False) == 1.0
    by_year = si._windowed(
        [{"pd": "01/06/2024", "v": 1.0, "et": "Rendimento"},
         {"pd": "01/07/2024", "v": 3.0, "et": "Amortização"}]
    )
    assert by_year.get("2024") == 1.0


async def test_seasonality_divide_pela_janela_completa():
    """Pagador irregular (2 dos últimos 5 anos) tem a média dividida pela JANELA, não
    pelos anos com pagamento — senão o calendário superestima a renda dos irregulares."""
    from datetime import datetime, timezone

    from app.cache.store import Cache

    year = datetime.now(timezone.utc).year
    cache = Cache()
    cache.set(
        "statusinvest:pay:IRRE3",
        [
            # pagou só em 2 dos últimos 5 anos, sempre em maio, R$ 2,00
            {"pd": f"15/05/{year - 1}", "v": 2.0, "et": "Dividendo"},
            {"pd": f"15/05/{year - 3}", "v": 2.0, "et": "Dividendo"},
            # primeiro pagamento bem antigo => janela cheia de 5 anos
            {"pd": f"15/05/{year - 9}", "v": 2.0, "et": "Dividendo"},
        ],
        3600,
    )
    season = await si.monthly_seasonality("IRRE3", cache)
    assert abs(season[5] - (2.0 + 2.0) / 5) < 1e-9  # ÷ janela (5), não ÷ 2
    assert season[6] == 0.0


async def test_seasonality_recem_listada_divide_desde_estreia():
    from datetime import datetime, timezone

    from app.cache.store import Cache

    year = datetime.now(timezone.utc).year
    cache = Cache()
    cache.set(
        "statusinvest:pay:NOVA3",
        [{"pd": f"10/03/{year - 1}", "v": 1.2, "et": "Rendimento"}],
        3600,
    )
    season = await si.monthly_seasonality("NOVA3", cache)
    assert abs(season[3] - 1.2 / 1) < 1e-9  # estreou ano passado: divide por 1, não por 5
