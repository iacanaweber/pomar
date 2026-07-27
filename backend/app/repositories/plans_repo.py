"""Repositório de planos gerados (tabela plan_history — criada na v1, viva a partir da v4).

Persistir o plano fecha dois buracos de UX/estratégia:
- o plano não evapora mais ao navegar/fechar a aba (o POST /plan custa até 60s);
- nasce a trilha 'o que o Pomar recomendou vs o que eu executei' (ordens levam plan_id).
Retenção: mantém os últimos N planos (o histórico é memória de decisão, não log infinito).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.repositories.db import Database

_KEEP = 50  # planos mantidos


async def save(db: Database, request: Dict[str, Any], response: Dict[str, Any]) -> int:
    plan_id = await db.insert(
        """
        INSERT INTO plan_history (created_at, aporte, request_json, response_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            request.get("aporte"),
            json.dumps(request),
            json.dumps(response),
        ),
    )
    await db.execute(
        "DELETE FROM plan_history WHERE id NOT IN (SELECT id FROM plan_history ORDER BY id DESC LIMIT ?)",
        (_KEEP,),
    )
    return plan_id


async def latest(db: Database) -> Optional[Dict[str, Any]]:
    row = await db.fetchone(
        "SELECT id, created_at, response_json FROM plan_history ORDER BY id DESC LIMIT 1"
    )
    if not row:
        return None
    try:
        resp = json.loads(row["response_json"] or "{}")
    except (TypeError, ValueError):
        return None
    resp["plan_id"] = row["id"]
    resp["created_at"] = row["created_at"]
    return resp


async def list_recent(db: Database, limit: int = 20) -> List[Dict[str, Any]]:
    rows = await db.fetchall(
        "SELECT id, created_at, aporte, response_json FROM plan_history ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        n_suggested = None
        try:
            resp = json.loads(r["response_json"] or "{}")
            n_suggested = sum(1 for x in resp.get("ranking", []) if x.get("suggested"))
        except (TypeError, ValueError):
            pass
        out.append(
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "aporte": r["aporte"],
                "suggested_count": n_suggested,
            }
        )
    return out
