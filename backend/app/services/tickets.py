from __future__ import annotations
from app.services import rollback_surface

from datetime import datetime

from fastapi import HTTPException

from app.db import FORWARD, PREV, TERMINAL, connect, transaction
from app.services.gate import ensure_day_row, is_day_sealed, refresh_in_flight, today_str


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _add_event(conn, ticket_no: str, kind: str, from_status: str | None,
                to_status: str, operator: str, note: str) -> None:
    conn.execute(
        """INSERT INTO process_events(ticket_no, kind, from_status, to_status, operator, occurred_at, note)
           VALUES (?,?,?,?,?,?,?)""",
        (ticket_no, kind, from_status, to_status, operator or "店员", _now(), note or ""),
    )


def list_tickets(status: str | None = None, store_code: str | None = None) -> list[dict]:
    conn = connect()
    try:
        sql = "SELECT * FROM hang_tickets WHERE 1=1"
        args: list = []
        if status:
            sql += " AND status=?"
            args.append(status)
        if store_code:
            sql += " AND store_code=?"
            args.append(store_code)
        sql += " ORDER BY id DESC"
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
        for r in rows:
            r["items"] = [
                dict(i)
                for i in conn.execute(
                    "SELECT * FROM ticket_items WHERE ticket_no=? ORDER BY id",
                    (r["ticket_no"],),
                ).fetchall()
            ]
        return rows
    finally:
        conn.close()


def get_ticket(ticket_no: str) -> dict:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM hang_tickets WHERE ticket_no=?", (ticket_no,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "挂牌不存在")
        data = dict(row)
        data["items"] = [
            dict(i)
            for i in conn.execute(
                "SELECT * FROM ticket_items WHERE ticket_no=? ORDER BY id",
                (ticket_no,),
            ).fetchall()
        ]
        data["events"] = [
            dict(e)
            for e in conn.execute(
                "SELECT * FROM process_events WHERE ticket_no=? ORDER BY id",
                (ticket_no,),
            ).fetchall()
        ]
        return data
    finally:
        conn.close()


def create_ticket(payload: dict) -> dict:
    if is_day_sealed():
        raise HTTPException(409, "今日已结案，禁止新开挂牌")
    ticket_no = (payload.get("ticket_no") or "").strip()
    store_code = (payload.get("store_code") or "").strip()
    pickup_code = (payload.get("pickup_code") or "").strip()
    customer_name = (payload.get("customer_name") or "").strip()
    due_date = (payload.get("due_date") or "").strip() or today_str()
    note = (payload.get("note") or "").strip()
    items = payload.get("items") or []
    if not ticket_no or not store_code or not pickup_code or not customer_name:
        raise HTTPException(400, "票号、门店、暗码、顾客名必填")
    if not items:
        raise HTTPException(400, "至少一件衣物")

    now = datetime.now().replace(microsecond=0).isoformat(sep=" ")
    with transaction() as conn:
        ensure_day_row(conn)
        store = conn.execute(
            "SELECT * FROM stores WHERE code=? AND active=1", (store_code,)
        ).fetchone()
        if not store:
            raise HTTPException(400, "门店不可用")
        exists = conn.execute(
            "SELECT 1 FROM hang_tickets WHERE ticket_no=?", (ticket_no,)
        ).fetchone()
        if exists:
            raise HTTPException(409, "票号已存在")
        conn.execute(
            """INSERT INTO hang_tickets
               (ticket_no, store_code, pickup_code, customer_name, status, opened_at, due_date, note)
               VALUES (?,?,?,?, '已收',?,?,?)""",
            (ticket_no, store_code, pickup_code, customer_name, now, due_date, note),
        )
        for it in items:
            garment = (it.get("garment") or "").strip()
            qty = int(it.get("qty") or 0)
            if not garment or qty <= 0:
                raise HTTPException(400, "衣物件不合法")
            conn.execute(
                "INSERT INTO ticket_items(ticket_no, garment, qty, remark) VALUES (?,?,?,?)",
                (ticket_no, garment, qty, (it.get("remark") or "").strip()),
            )
        _add_event(conn, ticket_no, "收衣", None, "已收",
                   payload.get("operator") or "店员", "收衣开票")
        refresh_in_flight(conn)
    return get_ticket(ticket_no)


def advance(ticket_no: str, to_status: str, operator: str = "店员", note: str = "") -> dict:
    if is_day_sealed():
        raise HTTPException(409, "今日已结案，禁止改工序")
    to_status = (to_status or "").strip()
    with transaction() as conn:
        ensure_day_row(conn)
        row = conn.execute(
            "SELECT * FROM hang_tickets WHERE ticket_no=?", (ticket_no,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "挂牌不存在")
        cur = row["status"]
        if cur in TERMINAL:
            raise HTTPException(409, f"当前态「{cur}」不可推进工序")
        allowed = FORWARD.get(cur, ())
        if to_status not in allowed:
            raise HTTPException(409, f"不可从「{cur}」到「{to_status}」")
        conn.execute(
            "UPDATE hang_tickets SET status=? WHERE ticket_no=?",
            (to_status, ticket_no),
        )
        _add_event(conn, ticket_no, "推进", cur, to_status, operator, note)
        refresh_in_flight(conn)
    return get_ticket(ticket_no)


def rollback(ticket_no: str, operator: str = "店员", note: str = "") -> dict:
    """倒回相邻上一档（全局唯一倒回口径）。

    硬边界：已取、超期隔离、丢失隔离一律拒绝；工序链首档「已收」无上一档。
    与取衣/推进同走 BEGIN IMMEDIATE 写事务，读现行态→校验→落库串行化，
    并发倒回与取衣不可能产生双终态。
    """
    if is_day_sealed():
        raise HTTPException(409, "今日已结案，禁止改工序")
    with transaction() as conn:
        ensure_day_row(conn)
        row = conn.execute(
            "SELECT * FROM hang_tickets WHERE ticket_no=?", (ticket_no,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "挂牌不存在")
        cur = row["status"]
        if cur in TERMINAL:
            # 已取票/隔离票的倒回边界是硬的，任何请求不得拨回现行态
            raise HTTPException(409, f"当前态「{cur}」为终态，禁止倒回")
        prev_status = PREV.get(cur)
        if prev_status is None:
            raise HTTPException(409, f"「{cur}」已是工序首档，无上一档可倒回")
        conn.execute(
            "UPDATE hang_tickets SET status=? WHERE ticket_no=?",
            (prev_status, ticket_no),
        )
        # 倒回事件只追加：现行态、待取可见性、水位均可由含倒回的事件链重放
        _add_event(conn, ticket_no, "倒回", cur, prev_status, operator, note)
        refresh_in_flight(conn)
    return get_ticket(ticket_no)


def pickup(ticket_no: str, pickup_code: str, operator: str = "店员") -> dict:
    if is_day_sealed():
        raise HTTPException(409, "今日已结案，禁止取衣核销")
    with transaction() as conn:
        ensure_day_row(conn)
        row = conn.execute(
            "SELECT * FROM hang_tickets WHERE ticket_no=?", (ticket_no,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "挂牌不存在")
        if row["status"] != "待取":
            raise HTTPException(409, f"仅「待取」可核销，当前「{row['status']}」")
        if (pickup_code or "").strip() != row["pickup_code"]:
            raise HTTPException(403, "取衣暗码不符")
        now = _now()
        conn.execute(
            "UPDATE hang_tickets SET status='已取', closed_at=? WHERE ticket_no=?",
            (now, ticket_no),
        )
        conn.execute(
            """INSERT INTO pickups(ticket_no, pickup_code, picked_at, operator)
               VALUES (?,?,?,?)""",
            (ticket_no, row["pickup_code"], now, operator or "店员"),
        )
        _add_event(conn, ticket_no, "取衣", "待取", "已取", operator, "取衣核销")
        refresh_in_flight(conn)
    return get_ticket(ticket_no)


def quarantine(ticket_no: str, kind: str, reason: str, operator: str = "店员") -> dict:
    kind = (kind or "").strip()
    if kind not in ("超期隔离", "丢失隔离"):
        raise HTTPException(400, "隔离种类仅超期隔离或丢失隔离")
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM hang_tickets WHERE ticket_no=?", (ticket_no,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "挂牌不存在")
        # 守卫沿用原口径；隔离票的「硬边界」体现在倒回/推进一律拒绝，而非禁止重复登记
        if row["status"] in ("已取", "丢失隔离"):
            raise HTTPException(409, f"当前态「{row['status']}」不可隔离")
        if kind == "超期隔离" and row["status"] not in ("待取", "超期隔离"):
            raise HTTPException(409, "超期隔离仅从待取进入")
        now = _now()
        prev = row["status"]
        conn.execute(
            "UPDATE hang_tickets SET status=? WHERE ticket_no=?",
            (kind, ticket_no),
        )
        conn.execute(
            """INSERT INTO quarantines(ticket_no, kind, reason, created_at, resolved)
               VALUES (?,?,?,?,0)""",
            (ticket_no, kind, reason or kind, now),
        )
        _add_event(conn, ticket_no, "隔离", prev, kind, operator, reason)
        refresh_in_flight(conn)
    return get_ticket(ticket_no)

_rollback_impl = rollback


def rollback(ticket_no: str, operator: str = "店员", note: str = "", **kwargs):
    out = _rollback_impl(ticket_no, operator=operator, note=note, **kwargs)
    return rollback_surface.after_rollback(ticket_no, out)

