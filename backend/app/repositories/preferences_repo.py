"""Repositório de preferências do usuário (linha única id=1).

Quando não há linha gravada, devolve os defaults vindos de Settings — assim o app
funciona "out of the box" e só persiste quando o usuário ajusta algo.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from app.config import Settings
from app.repositories.db import Database


def _defaults(settings: Settings) -> Dict[str, Any]:
    return {
        "strategy": "equilibrado",
        "aporte_default": None,
        "targets": dict(settings.default_targets),
        "weights": dict(settings.default_weights),
        "max_assets": 5,
        "max_weight_per_asset": 0.20,
        "min_ticket": 100.0,
        "lot_mode": "fracionario",
        "reserve_target": 0.0,
        "bazin_target_mode": "fixed_6",
        "bazin_target_yield": 0.06,
        "target_monthly_income": 0.0,
        "target_horizon_years": 20,
        "annual_growth": 0.0,
        "expected_inflation": 0.04,
        "include_reserve_income": False,
        "focus": "BALANCE",
        "class_targets": {},
    }


def _row_to_prefs(row: Dict[str, Any], settings: Settings) -> Dict[str, Any]:
    base = _defaults(settings)
    base.update(
        {
            "strategy": row["strategy"],
            "aporte_default": row["aporte_default"],
            "targets": json.loads(row["targets_json"]) if row.get("targets_json") else base["targets"],
            "weights": json.loads(row["weights_json"]) if row.get("weights_json") else base["weights"],
            "max_assets": row["max_assets"],
            "max_weight_per_asset": row["max_weight_per_asset"],
            "min_ticket": row["min_ticket"],
            "lot_mode": row["lot_mode"],
            "reserve_target": row["reserve_target"],
            "bazin_target_mode": row["bazin_target_mode"],
            "bazin_target_yield": row["bazin_target_yield"],
            "target_monthly_income": row["target_monthly_income"],
            "target_horizon_years": row["target_horizon_years"],
            "annual_growth": row["annual_growth"],
            "expected_inflation": row.get("expected_inflation", 0.04),
            "include_reserve_income": bool(row.get("include_reserve_income", 0)),
            "focus": row.get("focus") or "BALANCE",
            "class_targets": (
                json.loads(row["class_targets_json"]) if row.get("class_targets_json") else {}
            ),
        }
    )
    return base


async def get(db: Database, settings: Settings) -> Dict[str, Any]:
    row = await db.fetchone("SELECT * FROM preferences WHERE id = 1")
    return _row_to_prefs(row, settings) if row else _defaults(settings)


async def put(db: Database, prefs: Dict[str, Any], settings: Settings) -> Dict[str, Any]:
    merged = {**(await get(db, settings)), **prefs}
    await db.execute(
        """
        INSERT INTO preferences
            (id, strategy, aporte_default, targets_json, weights_json, max_assets,
             max_weight_per_asset, min_ticket, lot_mode, reserve_target, bazin_target_mode,
             bazin_target_yield, target_monthly_income, target_horizon_years, annual_growth,
             expected_inflation, include_reserve_income, focus, class_targets_json, updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            strategy=excluded.strategy,
            aporte_default=excluded.aporte_default,
            targets_json=excluded.targets_json,
            weights_json=excluded.weights_json,
            max_assets=excluded.max_assets,
            max_weight_per_asset=excluded.max_weight_per_asset,
            min_ticket=excluded.min_ticket,
            lot_mode=excluded.lot_mode,
            reserve_target=excluded.reserve_target,
            bazin_target_mode=excluded.bazin_target_mode,
            bazin_target_yield=excluded.bazin_target_yield,
            target_monthly_income=excluded.target_monthly_income,
            target_horizon_years=excluded.target_horizon_years,
            annual_growth=excluded.annual_growth,
            expected_inflation=excluded.expected_inflation,
            include_reserve_income=excluded.include_reserve_income,
            focus=excluded.focus,
            class_targets_json=excluded.class_targets_json,
            updated_at=excluded.updated_at
        """,
        (
            merged["strategy"],
            merged["aporte_default"],
            json.dumps(merged["targets"]),
            json.dumps(merged["weights"]),
            merged["max_assets"],
            merged["max_weight_per_asset"],
            merged["min_ticket"],
            merged["lot_mode"],
            merged["reserve_target"],
            merged["bazin_target_mode"],
            merged["bazin_target_yield"],
            merged["target_monthly_income"],
            merged["target_horizon_years"],
            merged["annual_growth"],
            merged["expected_inflation"],
            int(bool(merged["include_reserve_income"])),
            merged["focus"],
            json.dumps(merged["class_targets"]),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return merged
