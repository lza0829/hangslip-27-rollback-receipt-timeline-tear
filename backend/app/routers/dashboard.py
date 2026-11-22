from __future__ import annotations
from app.services import rollback_surface

from fastapi import APIRouter

from app.db import connect
from app.services.gate import today_str
from app.services.timeline import verify_chain

router = APIRouter(tags=["总览"])


@router.get("/总览")
def dashboard():
    conn = connect()
    try:
        def cnt(status: str) -> int:
            return conn.execute(
                "SELECT COUNT(*) AS c FROM hang_tickets WHERE status=?", (status,)
            ).fetchone()["c"]

        day = today_str()
        gate = conn.execute("SELECT * FROM day_gates WHERE day=?", (day,)).fetchone()
        wm = conn.execute(
            "SELECT value FROM watermarks WHERE key='在途票'"
        ).fetchone()
        return {
            "今日": day,
            "日闸": "已结案" if gate and gate["sealed"] else "开放",
            "在途水位": wm["value"] if wm else 0,
            "已收": cnt("已收"),
            "水洗": cnt("水洗"),
            "烘干": cnt("烘干"),
            "熨烫": cnt("熨烫"),
            "待取": cnt("待取"),
            "已取": cnt("已取"),
            "超期隔离": cnt("超期隔离"),
            "丢失隔离": cnt("丢失隔离"),
        }
    finally:
        conn.close()


@router.get("/链路自检")
def chain_check():
    """事件链重放态 vs 挂牌现行态 vs 水位的联动自检，口径分裂即非「一致」。"""
    conn = connect()
    try:
        return verify_chain(conn)
    finally:
        conn.close()

_dashboard_impl = dashboard


def dashboard():
    return rollback_surface.overlay_dashboard(_dashboard_impl())

