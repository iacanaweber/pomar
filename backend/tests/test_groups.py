"""Testes do agrupamento de tickers (substituição de ativo)."""
from __future__ import annotations

from app.services.groups import (
    also_tickers,
    all_tickers_in_groups,
    expand_all_baskets,
    expand_basket,
    merge_held,
)


def test_expand_basket_plain_floats():
    bw, grps = expand_basket({"IMAB11": 0.5, "MUND11": 0.5})
    assert bw == {"IMAB11": 0.5, "MUND11": 0.5}
    assert grps == {}


def test_expand_basket_with_also():
    bw, grps = expand_basket({
        "MUND11": {"weight": 0.5, "also": ["VWRA11"]},
        "IMAB11": 0.5,
    })
    assert bw == {"MUND11": 0.5, "IMAB11": 0.5}
    assert grps == {"MUND11": ["VWRA11"]}


def test_expand_basket_also_empty_list():
    bw, grps = expand_basket({"MUND11": {"weight": 0.5, "also": []}})
    assert bw == {"MUND11": 0.5}
    assert grps == {}


def test_merge_held_folds_legacy_into_buy():
    held = {"VWRA11": 8000.0, "MUND11": 2000.0, "IMAB11": 5000.0}
    result = merge_held(held, {"MUND11": ["VWRA11"]})
    assert result == {"MUND11": 10000.0, "IMAB11": 5000.0}
    assert "VWRA11" not in result


def test_merge_held_legacy_not_held():
    held = {"MUND11": 2000.0}
    result = merge_held(held, {"MUND11": ["VWRA11"]})
    assert result == {"MUND11": 2000.0}


def test_merge_held_buy_not_held():
    held = {"VWRA11": 8000.0}
    result = merge_held(held, {"MUND11": ["VWRA11"]})
    assert result == {"MUND11": 8000.0}


def test_merge_held_no_groups():
    held = {"AAA11": 1000.0}
    assert merge_held(held, {}) == {"AAA11": 1000.0}


def test_all_tickers_in_groups():
    groups = {"MUND11": ["VWRA11", "WRLD11"]}
    assert all_tickers_in_groups(groups) == {"MUND11", "VWRA11", "WRLD11"}


def test_also_tickers():
    groups = {"MUND11": ["VWRA11"], "IVVB11": ["SPX11"]}
    assert also_tickers(groups) == {"VWRA11", "SPX11"}


def test_expand_all_baskets():
    all_baskets = {
        "ETF": {
            "MUND11": {"weight": 0.5, "also": ["VWRA11"]},
            "IMAB11": 0.5,
        },
        "FII": {"HGLG11": 0.5, "XPML11": 0.5},
    }
    flat, groups = expand_all_baskets(all_baskets)
    assert flat == {
        "ETF": {"MUND11": 0.5, "IMAB11": 0.5},
        "FII": {"HGLG11": 0.5, "XPML11": 0.5},
    }
    assert groups == {"ETF": {"MUND11": ["VWRA11"]}}
