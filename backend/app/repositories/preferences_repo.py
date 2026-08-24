"""Repositório de preferências do usuário (linha única id=1).

Quando não há linha gravada, devolve os defaults vindos de Settings — assim o app
funciona "out of the box" e só persiste quando o usuário ajusta algo.

Colunas aposentadas: `strategy`, `weights_json`, `max_assets`, `max_weight_per_asset`,
`focus`, `target_monthly_income`, `target_horizon_years`, `annual_growth` e, desde a v8,
`reserve_target`. Migração em SQLite é aditiva — nunca dropamos coluna aplicada; elas
apenas deixaram de ser lidas. `reserve_target` era a fração do patrimônio em renda fixa e
virou o PISO em R$ da classe `RENDA_FIXA` (`reserve_floor_amount`); a conversão automática
de uma para a outra não tem significado, então o que a v8 faz é semear o PESO da classe
com o valor antigo (ver `seed_renda_fixa_from_reserve_target`) e pedir o piso uma vez.
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
        "reserve_target": 0.0,  # aposentado; ver docstring do módulo
        "bazin_target_mode": "fixed_6",
        "bazin_target_yield": 0.06,
        "class_targets": {},
        "reserve_floor_amount": 0.0,
        "reserve_floor_date": None,
        "reserve_floor_index": "none",
        "legacy_in_total": True,
        "dimension_targets": {},
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
            "reserve_floor_amount": row.get("reserve_floor_amount") or 0.0,
            "reserve_floor_date": row.get("reserve_floor_date"),
            "reserve_floor_index": row.get("reserve_floor_index") or "none",
            "legacy_in_total": bool(
                row["legacy_in_total"] if row.get("legacy_in_total") is not None else 1
            ),
            "dimension_targets": (
                json.loads(row["dimension_targets_json"])
                if row.get("dimension_targets_json")
                else {}
            ),
        }
    )
    return base


RENDA_FIXA = "RENDA_FIXA"


async def seed_renda_fixa_from_reserve_target(db: Database, settings: Settings) -> bool:
    """Converte o mecanismo aposentado em peso da classe `RENDA_FIXA` — uma vez só.

    O `reserve_target` NÃO vira piso: converter uma fração do patrimônio em um valor em R$
    não tem significado. Mas o que ele dizia — "esta fração do patrimônio fica em renda
    fixa" — é exatamente um PESO DE CLASSE, e é para lá que ele vai; as demais classes são
    renormalizadas por (1 − reserve_target) para a soma continuar fechando 100%. O piso
    nasce em zero e a interface o pede uma vez.

    Idempotente por construção: depois de rodar, `targets` tem a chave `RENDA_FIXA` e a
    condição de entrada deixa de valer. Devolve True se semeou agora.
    """
    prefs = await get(db, settings)
    legado = float(prefs.get("reserve_target") or 0.0)
    targets = dict(prefs.get("targets") or {})
    if legado <= 0 or RENDA_FIXA in targets:
        return False
    fator = max(0.0, 1.0 - legado)
    novos = {c: round(w * fator, 6) for c, w in targets.items()}
    novos[RENDA_FIXA] = round(legado, 6)
    await put(db, {"targets": novos}, settings)
    return True


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
             bazin_target_mode, bazin_target_yield, class_targets_json,
             reserve_floor_amount, reserve_floor_date, reserve_floor_index, legacy_in_total,
             dimension_targets_json, updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            aporte_default=excluded.aporte_default,
            targets_json=excluded.targets_json,
            min_ticket=excluded.min_ticket,
            lot_mode=excluded.lot_mode,
            reserve_target=excluded.reserve_target,
            bazin_target_mode=excluded.bazin_target_mode,
            bazin_target_yield=excluded.bazin_target_yield,
            class_targets_json=excluded.class_targets_json,
            reserve_floor_amount=excluded.reserve_floor_amount,
            reserve_floor_date=excluded.reserve_floor_date,
            reserve_floor_index=excluded.reserve_floor_index,
            legacy_in_total=excluded.legacy_in_total,
            dimension_targets_json=excluded.dimension_targets_json,
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
            merged["reserve_floor_amount"],
            merged["reserve_floor_date"],
            merged["reserve_floor_index"],
            int(bool(merged["legacy_in_total"])),
            json.dumps(merged["dimension_targets"]),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return merged
