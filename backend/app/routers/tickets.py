from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services import tickets as svc

router = APIRouter(tags=["挂牌"])


class ItemIn(BaseModel):
    garment: str
    qty: int = Field(ge=1)
    remark: str = ""


class TicketIn(BaseModel):
    ticket_no: str
    store_code: str
    pickup_code: str
    customer_name: str
    due_date: str = ""
    note: str = ""
    operator: str = "店员"
    items: list[ItemIn]


class AdvanceIn(BaseModel):
    to_status: str
    operator: str = "店员"
    note: str = ""


class RollbackIn(BaseModel):
    operator: str = "店员"
    note: str = ""


class PickupIn(BaseModel):
    pickup_code: str
    operator: str = "店员"


class QuarantineIn(BaseModel):
    kind: str
    reason: str = ""
    operator: str = "店员"


@router.get("/挂牌")
def list_tickets(
    status: str | None = Query(None),
    store_code: str | None = Query(None),
):
    return svc.list_tickets(status=status, store_code=store_code)


@router.get("/挂牌/{ticket_no}")
def get_ticket(ticket_no: str):
    return svc.get_ticket(ticket_no)


@router.post("/挂牌")
def create_ticket(body: TicketIn):
    return svc.create_ticket(body.model_dump())


@router.post("/挂牌/{ticket_no}/推进")
def advance(ticket_no: str, body: AdvanceIn):
    return svc.advance(ticket_no, body.to_status, body.operator, body.note)


@router.post("/挂牌/{ticket_no}/倒回")
def rollback(ticket_no: str, body: RollbackIn):
    return svc.rollback(ticket_no, body.operator, body.note)


@router.post("/挂牌/{ticket_no}/取衣")
def pickup(ticket_no: str, body: PickupIn):
    return svc.pickup(ticket_no, body.pickup_code, body.operator)


@router.post("/挂牌/{ticket_no}/隔离")
def quarantine(ticket_no: str, body: QuarantineIn):
    return svc.quarantine(ticket_no, body.kind, body.reason, body.operator)
