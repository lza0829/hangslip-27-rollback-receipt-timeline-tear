from __future__ import annotations

from datetime import date, datetime, timedelta

from app.db import PROCESS_CHAIN, connect, init_db


def seed_if_empty() -> None:
    init_db()
    conn = connect()
    try:
        n = conn.execute("SELECT COUNT(*) AS c FROM stores").fetchone()["c"]
        if n:
            return
        stores = [
            ("店-河西", "河西干洗", 3),
            ("店-城东", "城东快洗", 2),
            ("店-南苑", "南苑精洗", 4),
        ]
        for code, name, racks in stores:
            conn.execute(
                "INSERT INTO stores(code, name, rack_count, active) VALUES (?,?,?,1)",
                (code, name, racks),
            )

        today = date.today()
        opened = datetime.now().replace(microsecond=0).isoformat(sep=" ")
        samples = [
            ("挂-1001", "店-河西", "暗码甲七", "周小姐", "待取", today.isoformat(), "衬衣两件"),
            ("挂-1002", "店-河西", "暗码乙三", "陈先生", "水洗", (today + timedelta(days=1)).isoformat(), "大衣"),
            ("挂-1003", "店-城东", "暗码丙九", "王女士", "已收", (today + timedelta(days=2)).isoformat(), "西装套装"),
            ("挂-1004", "店-南苑", "暗码丁二", "李先生", "熨烫", today.isoformat(), "连衣裙"),
            ("挂-1005", "店-南苑", "暗码戊五", "赵小姐", "待取", (today - timedelta(days=2)).isoformat(), "羽绒服"),
            ("挂-1006", "店-城东", "暗码己八", "孙先生", "已取", (today - timedelta(days=1)).isoformat(), "衬衫"),
        ]
        items = {
            "挂-1001": [("衬衣", 2, "")],
            "挂-1002": [("大衣", 1, "防水")],
            "挂-1003": [("西装上衣", 1, ""), ("西装裤", 1, "")],
            "挂-1004": [("连衣裙", 1, "轻熨")],
            "挂-1005": [("羽绒服", 1, "充绒")],
            "挂-1006": [("衬衫", 3, "")],
        }
        for ticket_no, store, code, cust, status, due, note in samples:
            closed = opened if status == "已取" else None
            conn.execute(
                """INSERT INTO hang_tickets
                   (ticket_no, store_code, pickup_code, customer_name, status, opened_at, due_date, closed_at, note)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (ticket_no, store, code, cust, status, opened, due, closed, note),
            )
            for garment, qty, remark in items[ticket_no]:
                conn.execute(
                    "INSERT INTO ticket_items(ticket_no, garment, qty, remark) VALUES (?,?,?,?)",
                    (ticket_no, garment, qty, remark),
                )
            # 补完整前进事件链，保证重放末态 == 挂牌现行态（含倒回口径下自检可过）
            chain_target = "待取" if status == "已取" else status
            chain = list(PROCESS_CHAIN[: PROCESS_CHAIN.index(chain_target) + 1])
            conn.execute(
                """INSERT INTO process_events(ticket_no, kind, from_status, to_status, operator, occurred_at, note)
                   VALUES (?,?,?,?,?,?,?)""",
                (ticket_no, "收衣", None, chain[0], "开店员", opened, "种子"),
            )
            for prev_st, next_st in zip(chain, chain[1:]):
                conn.execute(
                    """INSERT INTO process_events(ticket_no, kind, from_status, to_status, operator, occurred_at, note)
                       VALUES (?,?,?,?,?,?,?)""",
                    (ticket_no, "推进", prev_st, next_st, "开店员", opened, "种子"),
                )
            if status == "已取":
                conn.execute(
                    """INSERT INTO pickups(ticket_no, pickup_code, picked_at, operator)
                       VALUES (?,?,?,?)""",
                    (ticket_no, code, opened, "开店员"),
                )
                conn.execute(
                    """INSERT INTO process_events(ticket_no, kind, from_status, to_status, operator, occurred_at, note)
                       VALUES (?,?,?,?,?,?,?)""",
                    (ticket_no, "取衣", "待取", "已取", "开店员", opened, "种子取衣"),
                )

        conn.execute(
            "INSERT INTO day_gates(day, sealed, sealed_at, note) VALUES (?,?,?,?)",
            (today.isoformat(), 0, None, ""),
        )
        conn.execute(
            "INSERT INTO settings(key, value) VALUES ('当前门店', ?)",
            ("店-河西",),
        )
        # 水位由事件链重放派生，与运行期 refresh_in_flight 同一口径
        from app.services.gate import refresh_in_flight

        refresh_in_flight(conn)
        conn.commit()
    finally:
        conn.close()
