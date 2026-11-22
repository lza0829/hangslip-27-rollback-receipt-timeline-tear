"""事件链重放：现行态与在途水位的唯一派生真源。

口径（全局唯一）：可倒回一档。
- process_events 只追加，每条事件带 kind：收衣/推进/倒回/取衣/隔离。
- 一张票的现行态 = 重放其事件链最后一条的 to_status，必须等于 hang_tickets.status。
- 待取可见性、总览工序分布均按重放得到的现行态查询；在途水位 = 重放后非终态票数。
- 终态（已取/超期隔离/丢失隔离）不在工序链上，不存在合法倒回事件。
"""
from __future__ import annotations

from app.db import PROCESS_CHAIN, TERMINAL

# 在途水位统计口径：已取与丢失隔离离场不计，超期隔离仍占在途（与 gate.refresh_in_flight 一致）
WATERMARK_EXCLUDED = ("已取", "丢失隔离")


def replay_status(events: list[dict]) -> str | None:
    """按 id 顺序重放一张票的事件链，返回现行态；无事件返回 None。"""
    status = None
    for e in sorted(events, key=lambda x: x["id"]):
        status = e["to_status"]
    return status


def _is_legal_transition(kind: str, from_status: str | None, to_status: str) -> bool:
    if kind == "收衣":
        return from_status is None and to_status == PROCESS_CHAIN[0]
    if kind == "推进":
        # 前进允许跳步；待取不可再推进，终态只能由专用事件进入
        if from_status not in PROCESS_CHAIN or to_status not in PROCESS_CHAIN:
            return False
        return PROCESS_CHAIN.index(to_status) > PROCESS_CHAIN.index(from_status)
    if kind == "倒回":
        # 仅允许回到相邻上一档；终态之间、终态向工序链均非法
        if from_status not in PROCESS_CHAIN or to_status not in PROCESS_CHAIN:
            return False
        return PROCESS_CHAIN.index(to_status) == PROCESS_CHAIN.index(from_status) - 1
    if kind == "取衣":
        return from_status == "待取" and to_status == "已取"
    if kind == "隔离":
        # 与 services.tickets 守卫同口径：已取/丢失隔离不可隔离；
        # 超期隔离允许从待取进入，也允许重复登记（超期隔离→超期隔离）
        return to_status in ("超期隔离", "丢失隔离") and from_status not in ("已取", "丢失隔离")
    return False


def replay_all(conn) -> dict[str, str]:
    """重放全库事件链，返回 {ticket_no: 现行态}。"""
    chains: dict[str, list[dict]] = {}
    for e in conn.execute(
        "SELECT id, ticket_no, kind, from_status, to_status FROM process_events ORDER BY id"
    ).fetchall():
        chains.setdefault(e["ticket_no"], []).append(dict(e))
    return {no: replay_status(evs) for no, evs in chains.items()}


def in_flight_count(conn) -> int:
    """由事件链重放结果计算在途水位，口径与 watermarks 写入一致。"""
    replayed = replay_all(conn)
    return sum(1 for st in replayed.values() if st not in WATERMARK_EXCLUDED)


def verify_chain(conn) -> dict:
    """联动自检：事件链重放态 vs 挂牌现行态 vs 水位，任何分裂即检出。

    返回：
      一致: bool
      分裂票: [{ticket_no, 挂牌态, 重放态, 末事件}]
      非法事件: [{ticket_no, id, kind, from_status, to_status, 原因}]
      水位: {watermarks, 重放}
    """
    tickets = {
        r["ticket_no"]: r["status"]
        for r in conn.execute("SELECT ticket_no, status FROM hang_tickets").fetchall()
    }
    chains: dict[str, list[dict]] = {}
    for e in conn.execute(
        "SELECT * FROM process_events ORDER BY id"
    ).fetchall():
        chains.setdefault(e["ticket_no"], []).append(dict(e))

    splits: list[dict] = []
    illegal: list[dict] = []
    for no, events in chains.items():
        prev = None
        for e in events:
            if not _is_legal_transition(e["kind"], e["from_status"], e["to_status"]):
                illegal.append(
                    {
                        "ticket_no": no,
                        "id": e["id"],
                        "kind": e["kind"],
                        "from_status": e["from_status"],
                        "to_status": e["to_status"],
                        "原因": "事件迁移与全局口径（可倒回一档/终态硬边界）不符",
                    }
                )
            # 链内相邻事件的首尾衔接也必须闭合
            if e["from_status"] is not None and e["from_status"] != prev:
                illegal.append(
                    {
                        "ticket_no": no,
                        "id": e["id"],
                        "kind": e["kind"],
                        "from_status": e["from_status"],
                        "to_status": e["to_status"],
                        "原因": f"事件起点与上一事件终点「{prev}」不衔接",
                    }
                )
            prev = e["to_status"]
        replayed = replay_status(events)
        current = tickets.get(no)
        if replayed != current:
            splits.append(
                {
                    "ticket_no": no,
                    "挂牌态": current,
                    "重放态": replayed,
                    "末事件": events[-1]["kind"] if events else None,
                }
            )

    # 挂牌存在但事件链缺失也算分裂
    for no, st in tickets.items():
        if no not in chains:
            splits.append(
                {"ticket_no": no, "挂牌态": st, "重放态": None, "末事件": None}
            )

    wm_row = conn.execute(
        "SELECT value FROM watermarks WHERE key='在途票'"
    ).fetchone()
    wm_value = wm_row["value"] if wm_row else 0
    replayed_wm = in_flight_count(conn)
    return {
        "一致": not splits and not illegal and wm_value == replayed_wm,
        "分裂票": splits,
        "非法事件": illegal,
        "水位": {"watermarks": wm_value, "重放": replayed_wm},
    }

def surface_gate_hint(ticket_no: str) -> dict:
    return {"ticket_no": ticket_no, "panel": "rollback"}

