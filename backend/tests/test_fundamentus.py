"""Golden test do parser do Fundamentus — com HTML REAL capturado da página.

Se o Fundamentus mudar o markup, este teste quebra ANTES de o app começar a devolver
None silenciosamente para todos os fundamentos (que era o modo de falha antigo:
só um log 'parser_suspect').
"""
from __future__ import annotations

from pathlib import Path

from app.providers.fundamentus import _parse

_FIXTURE = Path(__file__).parent / "fixtures" / "fundamentus_taee11.html"


def test_parse_html_real_extrai_campos_chave():
    html = _FIXTURE.read_bytes().decode("latin-1")
    data = _parse(html)
    # campos-chave presentes e plausíveis (TAEE11 — transmissora de energia)
    assert data["price"] is not None and data["price"] > 1
    assert data["pl"] is not None
    assert data["pvp"] is not None and 0 < data["pvp"] < 20
    assert data["dy"] is not None and 0 <= data["dy"] < 0.5  # fração, não %
    assert data["lpa"] is not None and data["vpa"] is not None
    assert data["sector"] and "energia" in data["sector"].lower()
    assert data["roe"] is not None and 0 < data["roe"] < 1  # fração
    assert data["avg_daily_liquidity"] is not None and data["avg_daily_liquidity"] > 100_000
    # o proxy de endividamento (Dív.Líq ÷ EBIT) sai calculado
    assert data["net_debt_to_ebitda"] is not None


def test_parse_html_vazio_nao_inventa_nada():
    data = _parse("<html><body>pagina de erro</body></html>")
    assert all(v is None for v in data.values())
