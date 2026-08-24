"""Rotas dos rótulos: dimensões, criação livre e atribuição a tickers e contas.

A dimensão `bucket` é a única que muda o que o app compra (ela sobrepõe a classificação
automática); `indexer` e `geography` descrevem. `include_defaults=true` na listagem faz a
resposta trazer também o rótulo HERDADO do mapa curado para os sujeitos que o usuário nunca
tocou — é o que permite à interface mostrar "Brasil (default)" em vez de um campo vazio,
sem gravar nada no banco por antecipação.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.data import geography
from app.deps import get_db
from app.models.labels import AssignmentOut, AssignmentsIn, LabelIn, LabelOut
from app.repositories import labels_repo as repo

router = APIRouter()


def _fail(exc: Exception) -> HTTPException:
    """ValueError é pedido inválido (422); LookupError é sujeito inexistente (404)."""
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/labels", response_model=List[LabelOut])
async def list_labels(dimension: Optional[str] = None) -> List[LabelOut]:
    try:
        rows = await repo.list_labels(get_db(), dimension)
    except ValueError as exc:
        raise _fail(exc) from exc
    return [LabelOut(**r) for r in rows]


@router.post("/labels", response_model=LabelOut)
async def create_label(body: LabelIn) -> LabelOut:
    try:
        row = await repo.create_label(get_db(), body.dimension, body.code, body.name or "")
    except (ValueError, LookupError) as exc:
        raise _fail(exc) from exc
    return LabelOut(**row)


# As rotas de /labels/assignments vêm ANTES de /labels/{label_id}: declaradas depois, um
# DELETE em /labels/assignments casaria com o path de id e morreria tentando ler um int.
@router.get("/labels/assignments", response_model=List[AssignmentOut])
async def list_assignments(
    dimension: Optional[str] = None,
    subject_type: Optional[str] = None,
    subject_id: Optional[str] = None,
    subjects: Optional[str] = Query(
        None, description="Lista separada por vírgula — resolve vários sujeitos de uma vez."
    ),
    include_defaults: bool = Query(
        False, description="Inclui o rótulo herdado do mapa curado para quem não tem escolha gravada."
    ),
) -> List[AssignmentOut]:
    wanted = [s.strip() for s in (subjects or "").split(",") if s.strip()]
    if subject_id:
        wanted = [subject_id]
    try:
        rows = await repo.list_assignments(
            get_db(),
            dimension=dimension,
            subject_type=subject_type,
            subject_id=subject_id,
            subject_ids=wanted or None,
        )
    except ValueError as exc:
        raise _fail(exc) from exc

    out = [
        AssignmentOut(
            id=r["id"], label_id=r["label_id"], subject_type=r["subject_type"],
            subject_id=r["subject_id"], dimension=r["dimension"], code=r["code"],
            name=r["name"], weight=float(r["weight"]), source="user",
        )
        for r in rows
    ]
    # Só a geografia tem default por ticker; as demais dimensões não herdam nada.
    if include_defaults and dimension == "geography" and subject_type == "ticker" and wanted:
        assigned = {r["subject_id"] for r in rows}
        for raw in wanted:
            key = repo.normalize_subject("ticker", raw)
            if key in assigned:
                continue
            code, source = geography.resolve(key)
            out.append(
                AssignmentOut(
                    subject_type="ticker", subject_id=key, dimension="geography",
                    code=code, name="Brasil" if code == "BR" else "Internacional",
                    weight=1.0, source=source,
                )
            )
    return out


@router.put("/labels/assignments", response_model=List[AssignmentOut])
async def set_assignments(body: AssignmentsIn) -> List[AssignmentOut]:
    try:
        rows = await repo.set_assignments(
            get_db(),
            body.subject_type,
            body.subject_id,
            body.dimension,
            [i.model_dump() for i in body.items],
        )
    except (ValueError, LookupError) as exc:
        raise _fail(exc) from exc
    return [
        AssignmentOut(
            id=r["id"], label_id=r["label_id"], subject_type=r["subject_type"],
            subject_id=r["subject_id"], dimension=r["dimension"], code=r["code"],
            name=r["name"], weight=float(r["weight"]), source="user",
        )
        for r in rows
    ]


@router.delete("/labels/assignments")
async def clear_assignments(subject_type: str, subject_id: str, dimension: str) -> dict:
    try:
        await repo.clear_assignments(get_db(), subject_type, subject_id, dimension)
    except ValueError as exc:
        raise _fail(exc) from exc
    return {"ok": True}


@router.delete("/labels/{label_id}")
async def delete_label(label_id: int) -> dict:
    try:
        await repo.delete_label(get_db(), label_id)
    except (ValueError, LookupError) as exc:
        raise _fail(exc) from exc
    return {"ok": True}
