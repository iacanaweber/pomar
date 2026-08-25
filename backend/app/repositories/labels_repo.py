"""Repositório dos rótulos e das atribuições (`labels` + `label_assignments`).

Um rótulo é (dimensão, código); uma atribuição liga um SUJEITO — um ticker ou uma conta de
renda fixa — a um rótulo, com peso. O peso existe para exposição parcial: um ETF global que
inclui o Brasil pode ser 60% `INTL` e 40% `BR`. Por isso a regra de integridade é por
dimensão: os pesos de uma mesma dimensão, para um mesmo sujeito, somam 1.0.

A dimensão `bucket` é a exceção e aceita UM rótulo só, com peso 1.0: ela decide em que
cesta o ativo é comprado, e "40% em Ações" não é uma cesta — é uma indecisão que o
alocador não teria como respeitar.

Rótulo órfão (o Ghostfolio parou de devolver o ticker) nunca é apagado automaticamente: o
rótulo é local, e sobreviver ao provedor é o comportamento desejado.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.data.labels_seed import BUCKET_LABELS, BUILTIN_LABELS, DIMENSIONS
from app.repositories.db import Database
from app.util import looks_like_ticker, normalize_ticker

# As cinco classes da carteira alvo. Um `bucket` fora desta lista viraria
# `asset_class` sem ter peso, rótulo nem lugar no alocador.
_BUCKET_CODES = {code for code, _ in BUCKET_LABELS}

SUBJECT_TYPES = ("ticker", "fi_account")

# Mesma tolerância do validador da carteira alvo em `routes_preferences`.
WEIGHT_TOLERANCE = 0.001

_SELECT_ASSIGNMENT = """
    SELECT la.id, la.subject_type, la.subject_id, la.label_id, la.weight, la.created_at,
           l.dimension, l.code, l.name, l.builtin
      FROM label_assignments la
      JOIN labels l ON l.id = la.label_id
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_subject(subject_type: str, subject_id: str) -> str:
    """Chave canônica do sujeito: ticker pela `normalize_ticker`, conta pelo id como texto."""
    if subject_type == "ticker":
        return normalize_ticker(subject_id)
    return str(subject_id).strip()


def _check_dimension(dimension: str) -> str:
    d = (dimension or "").strip().lower()
    if d not in DIMENSIONS:
        raise ValueError(f"dimensão '{dimension}' desconhecida; use {', '.join(DIMENSIONS)}.")
    return d


def _check_subject_type(subject_type: str) -> str:
    s = (subject_type or "").strip().lower()
    if s not in SUBJECT_TYPES:
        raise ValueError(f"subject_type '{subject_type}' inválido; use {', '.join(SUBJECT_TYPES)}.")
    return s


# --- rótulos ---

async def ensure_builtins(db: Database) -> int:
    """Semeia os rótulos embutidos. Idempotente; devolve quantos foram criados agora.

    A contagem serve de atalho: depois do primeiro boot toda leitura de rótulo custa uma
    query só, em vez de repetir catorze `INSERT OR IGNORE`.
    """
    row = await db.fetchone("SELECT COUNT(*) AS n FROM labels WHERE builtin = 1")
    before = row["n"] if row else 0
    if before >= len(BUILTIN_LABELS):
        return 0
    for dimension, code, name in BUILTIN_LABELS:
        await db.execute(
            """INSERT OR IGNORE INTO labels (dimension, code, name, builtin, created_at)
               VALUES (?, ?, ?, 1, ?)""",
            (dimension, code, name, _now()),
        )
    after = await db.fetchone("SELECT COUNT(*) AS n FROM labels WHERE builtin = 1")
    return (after["n"] if after else 0) - before


async def list_labels(db: Database, dimension: Optional[str] = None) -> List[Dict[str, Any]]:
    await ensure_builtins(db)
    if dimension:
        return await db.fetchall(
            "SELECT * FROM labels WHERE dimension = ? ORDER BY builtin DESC, code",
            (_check_dimension(dimension),),
        )
    return await db.fetchall("SELECT * FROM labels ORDER BY dimension, builtin DESC, code")


async def get_label(db: Database, label_id: int) -> Optional[Dict[str, Any]]:
    return await db.fetchone("SELECT * FROM labels WHERE id = ?", (int(label_id),))


async def find_label(db: Database, dimension: str, code: str) -> Optional[Dict[str, Any]]:
    await ensure_builtins(db)
    return await db.fetchone(
        "SELECT * FROM labels WHERE dimension = ? AND code = ?",
        (_check_dimension(dimension), (code or "").strip().upper()),
    )


async def create_label(db: Database, dimension: str, code: str, name: str) -> Dict[str, Any]:
    d = _check_dimension(dimension)
    c = (code or "").strip().upper().replace(" ", "_")
    n = (name or "").strip() or c
    if not c:
        raise ValueError("o código do rótulo é obrigatório.")
    # A dimensão `bucket` são as CLASSES da carteira alvo, e só elas: o código vira
    # `asset_class` verbatim em `classify.classify_ticker`, e uma sexta classe não teria
    # peso em `targets`, nem rótulo em `CLASS_LABEL`, nem lugar no alocador — o ativo
    # atribuído a ela sumiria do plano em silêncio.
    if d == "bucket" and c not in _BUCKET_CODES:
        raise ValueError(
            "a dimensão 'bucket' são as classes da carteira alvo (Ações, FIIs, ETFs, "
            "BDRs, Renda fixa); não há rótulo novo a criar."
        )
    # Um código de indexador com forma de ticker seria lido como TICKER pela cesta de
    # renda fixa (ver `util.looks_like_ticker`) e o dinheiro daquela tag sumiria dela.
    if d == "indexer" and looks_like_ticker(c):
        raise ValueError(
            f"'{c}' tem forma de ticker da B3. Na cesta de renda fixa um ticker é o "
            "próprio item, não um indexador — use um código sem essa forma."
        )
    existing = await find_label(db, d, c)
    if existing:
        raise ValueError(f"já existe o rótulo {c} na dimensão {d}.")
    await db.insert(
        "INSERT INTO labels (dimension, code, name, builtin, created_at) VALUES (?, ?, ?, 0, ?)",
        (d, c, n, _now()),
    )
    return await find_label(db, d, c)  # type: ignore[return-value]


async def delete_label(db: Database, label_id: int) -> None:
    """Apaga um rótulo do usuário (as atribuições caem por ON DELETE CASCADE).

    Embutido não se apaga: as telas contam com a existência de `CDI`, `BR` e companhia.
    """
    label = await get_label(db, label_id)
    if label is None:
        raise LookupError("rótulo não encontrado.")
    if label["builtin"]:
        raise ValueError(f"'{label['code']}' é um rótulo embutido e não pode ser removido.")
    await db.execute("DELETE FROM label_assignments WHERE label_id = ?", (int(label_id),))
    await db.execute("DELETE FROM labels WHERE id = ?", (int(label_id),))


# --- atribuições ---

async def list_assignments(
    db: Database,
    *,
    dimension: Optional[str] = None,
    subject_type: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    await ensure_builtins(db)
    where: List[str] = []
    params: List[Any] = []
    if dimension:
        where.append("l.dimension = ?")
        params.append(_check_dimension(dimension))
    if subject_type:
        st = _check_subject_type(subject_type)
        where.append("la.subject_type = ?")
        params.append(st)
        if subject_id:
            where.append("la.subject_id = ?")
            params.append(normalize_subject(st, subject_id))
        elif subject_ids:
            keys = [normalize_subject(st, s) for s in subject_ids]
            where.append(f"la.subject_id IN ({', '.join('?' for _ in keys)})")
            params.extend(keys)
    sql = _SELECT_ASSIGNMENT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY la.subject_id, l.dimension, l.code"
    return await db.fetchall(sql, tuple(params))


def _validate_items(dimension: str, items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[int] = set()
    for item in items:
        label_id = int(item["label_id"])
        if label_id in seen:
            raise ValueError("o mesmo rótulo aparece duas vezes na atribuição.")
        seen.add(label_id)
        weight = float(item.get("weight", 1.0))
        if weight <= 0:
            raise ValueError("peso de rótulo deve ser > 0.")
        out.append({"label_id": label_id, "weight": weight})
    if not out:
        return out
    if dimension == "bucket":
        if len(out) > 1:
            raise ValueError(
                "a dimensão 'bucket' aceita um rótulo só: é ela que decide em que cesta o "
                "ativo é comprado."
            )
        out[0]["weight"] = 1.0
        return out
    total = sum(i["weight"] for i in out)
    if abs(total - 1.0) > WEIGHT_TOLERANCE:
        raise ValueError(
            f"os pesos de '{dimension}' somam {total * 100:.1f}%, deveriam somar 100%."
        )
    return out


async def set_assignments(
    db: Database,
    subject_type: str,
    subject_id: str,
    dimension: str,
    items: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Substitui TODAS as atribuições daquela dimensão para aquele sujeito.

    Lista vazia limpa a dimensão (o sujeito volta a herdar o default, quando existe um).
    Tudo é validado ANTES de apagar qualquer coisa: se algum rótulo não existir ou os pesos
    não fecharem, o estado anterior fica intacto.
    """
    st = _check_subject_type(subject_type)
    d = _check_dimension(dimension)
    key = normalize_subject(st, subject_id)
    if not key:
        raise ValueError("sujeito da atribuição é obrigatório.")

    validated = _validate_items(d, list(items))
    for item in validated:
        label = await get_label(db, item["label_id"])
        if label is None:
            raise LookupError(f"rótulo {item['label_id']} não encontrado.")
        if label["dimension"] != d:
            raise ValueError(
                f"o rótulo {label['code']} é da dimensão '{label['dimension']}', não de '{d}'."
            )

    await clear_assignments(db, st, key, d)
    for item in validated:
        await db.insert(
            """INSERT INTO label_assignments
                   (subject_type, subject_id, label_id, weight, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (st, key, item["label_id"], item["weight"], _now()),
        )
    return await list_assignments(db, dimension=d, subject_type=st, subject_id=key)


async def clear_assignments(
    db: Database, subject_type: str, subject_id: str, dimension: str
) -> None:
    st = _check_subject_type(subject_type)
    d = _check_dimension(dimension)
    await db.execute(
        """DELETE FROM label_assignments
            WHERE subject_type = ? AND subject_id = ?
              AND label_id IN (SELECT id FROM labels WHERE dimension = ?)""",
        (st, normalize_subject(st, subject_id), d),
    )


# --- leituras agregadas (o que os serviços consomem) ---

async def assignments_by_subject(
    db: Database, dimension: str, subject_type: str
) -> Dict[str, List[Dict[str, Any]]]:
    """{sujeito: [{code, weight, name}]} — uma query só, para não consultar por ativo."""
    rows = await list_assignments(db, dimension=dimension, subject_type=subject_type)
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["subject_id"], []).append(
            {"code": r["code"], "name": r["name"], "weight": float(r["weight"])}
        )
    return out


async def bucket_overrides(db: Database) -> Dict[str, str]:
    """{ticker: CLASSE} escolhido à mão — o "passo zero" de `services/classify.py`."""
    rows = await list_assignments(db, dimension="bucket", subject_type="ticker")
    return {r["subject_id"]: r["code"] for r in rows}
