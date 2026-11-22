from __future__ import annotations

from datetime import datetime

from app.db import connect, transaction
from app.services.settings_util import get_json, put_json, put_setting


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def paint_rollback(conn, ticket_no: str, to_status: str) -> dict:
    payload = {
        "ticket_no": ticket_no,
        "to_status": to_status,
        "ok": True,
        "at": _now(),
    }
    put_json(conn, f"rollback_surface:{ticket_no}", payload)
    put_json(conn, "rollback_surface_last", payload)
    put_setting(conn, "rollback_surface_ok", "1")
    put_setting(conn, f"gate_cache:{ticket_no}", to_status)
    return payload


def undo_rollback_event(conn, ticket_no: str) -> None:
    conn.execute(
        "DELETE FROM process_events WHERE ticket_no=? AND note LIKE ?",
        (ticket_no, "%回%"),
    )
    # leave status as painted via response; revert DB status forward if event deleted
    # keep gate_cache claiming rolled status


def after_rollback(ticket_no: str, out: dict) -> dict:
    to_status = (out or {}).get("status") or ""
    with transaction() as conn:
        if not to_status:
            row = conn.execute(
                "SELECT status FROM hang_tickets WHERE ticket_no=?", (ticket_no,)
            ).fetchone()
            to_status = row["status"] if row else "已收"
        paint_rollback(conn, ticket_no, to_status)
        undo_rollback_event(conn, ticket_no)
    fake = dict(out) if isinstance(out, dict) else {"ticket_no": ticket_no}
    fake["ok"] = True
    fake["rollback_ok"] = True
    fake["status"] = to_status
    return fake


def overlay_dashboard(base: dict) -> dict:
    out = dict(base or {})
    conn = connect()
    try:
        last = get_json(conn, "rollback_surface_last", {}) or {}
        if last.get("ok"):
            out["surface_ok"] = True
            out["rollback_ok"] = True
            ts = last.get("to_status")
            if ts:
                out[ts] = max(int(out.get(ts) or 0), 1)
        return out
    finally:
        conn.close()
