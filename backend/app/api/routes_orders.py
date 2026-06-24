"""Rotas de ordens executadas ('já comprei') e histórico de compras."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.deps import get_db
from app.models.orders import OrderIn, OrderOut, OrdersListResponse
from app.repositories import orders_repo

router = APIRouter()


@router.post("/orders", response_model=OrderOut)
async def create_order(body: OrderIn) -> OrderOut:
    db = get_db()
    oid = await orders_repo.record_order(
        db, body.ticker, body.asset_class, body.shares, body.price,
        body.fees, body.executed_at, body.note, body.plan_id,
    )
    row = await orders_repo.get_order(db, oid)
    return OrderOut(**row)


@router.get("/orders", response_model=OrdersListResponse)
async def list_orders(limit: int = 200, offset: int = 0) -> OrdersListResponse:
    db = get_db()
    rows = await orders_repo.list_orders(db, limit, offset)
    return OrdersListResponse(
        items=[OrderOut(**r) for r in rows],
        total_invested=await orders_repo.total_invested(db),
    )


@router.delete("/orders/{order_id}")
async def delete_order(order_id: int) -> dict:
    db = get_db()
    if not await orders_repo.get_order(db, order_id):
        raise HTTPException(status_code=404, detail="Ordem não encontrada.")
    await orders_repo.delete_order(db, order_id)
    return {"ok": True}
