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
        "aporte_default": None,
        "targets": dict(settings.default_targets),
        "min_ticket": 100.0,
        "lot_mode": "fracionario",
        "reserve_target": 0.0,
        "bazin_target_mode": "fixed_6",
        "bazin_target_yield": 0.06,
        "class_targets": {},
    }


def _row_to_prefs(row: Dict[str, Any], settings: Settings) -> Dict[str, Any]:
    base = _defaults(settings)
    base.update(
        {
            "aporte_default": row["aporte_default"],
            "targets": json.loads(row["targets_json"]) if row.get("targets_json") else base["targets"],
            "min_ticket": row["min_ticket"],
            "lot_mode": row["lot_mode"],
            "reserve_target": row["reserve_target"],
            "bazin_target_mode": row["bazin_target_mode"],
            "bazin_target_yield": row["bazin_target_yield"],
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
    # As colunas de mecanismos aposentados (estratégia, pesos, foco, meta de renda…)
    # continuam no schema — migração SQLite é aditiva — mas saem do INSERT: os DEFAULTs
    # da tabela cobrem o NOT NULL e nenhum dado gravado precisa ser redigitado.
    await db.execute(
        """
        INSERT INTO preferences
            (id, aporte_default, targets_json, min_ticket, lot_mode, reserve_target,
             bazin_target_mode, bazin_target_yield, class_targets_json, updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            aporte_default=excluded.aporte_default,
            targets_json=excluded.targets_json,
            min_ticket=excluded.min_ticket,
            lot_mode=excluded.lot_mode,
            reserve_target=excluded.reserve_target,
            bazin_target_mode=excluded.bazin_target_mode,
            bazin_target_yield=excluded.bazin_target_yield,
            class_targets_json=excluded.class_targets_json,
            updated_at=excluded.updated_at
        """,
        (
            merged["aporte_default"],
            json.dumps(merged["targets"]),
            merged["min_ticket"],
            merged["lot_mode"],
            merged["reserve_target"],
            merged["bazin_target_mode"],
            merged["bazin_target_yield"],
            json.dumps(merged["class_targets"]),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return merged
