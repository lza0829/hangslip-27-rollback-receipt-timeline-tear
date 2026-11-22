from __future__ import annotations

import sqlite3

import app.config as config
from conftest import make_ticket


def _advance(client, no, to):
    assert client.post(f"/api/挂牌/{no}/推进", json={"to_status": to}).status_code == 200


def test_self_check_detects_status_event_split(client):
    make_ticket(client, "挂-I1")
    _advance(client, "挂-I1", "水洗")
    # 直接篡改挂牌现行态，制造“事件链只前进、现行态已回退”的分裂
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("UPDATE hang_tickets SET status='已收' WHERE ticket_no='挂-I1'")
    conn.commit()
    conn.close()

    body = client.get("/api/链路自检").json()
    assert body["一致"] is False
    assert any(s["ticket_no"] == "挂-I1" for s in body["分裂票"])


def test_self_check_detects_illegal_terminal_rollback(client):
    make_ticket(client, "挂-I2", code="暗码I2")
    _advance(client, "挂-I2", "待取")
    assert client.post(
        "/api/挂牌/挂-I2/取衣", json={"pickup_code": "暗码I2"}
    ).status_code == 200
    # 绕过服务层硬边界，直接写入一条“已取→待取”的倒回事件并拨回现行态
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        """INSERT INTO process_events(ticket_no, kind, from_status, to_status, operator, occurred_at, note)
           VALUES ('挂-I2','倒回','已取','待取','x','2026-11-22 00:00:00','篡改')"""
    )
    conn.execute("UPDATE hang_tickets SET status='待取' WHERE ticket_no='挂-I2'")
    conn.commit()
    conn.close()

    body = client.get("/api/链路自检").json()
    assert body["一致"] is False
    assert any(
        i["ticket_no"] == "挂-I2" and i["kind"] == "倒回" for i in body["非法事件"]
    )


def test_repeated_overdue_quarantine_is_legal(client):
    make_ticket(client, "挂-I3")
    _advance(client, "挂-I3", "待取")
    for _ in range(2):
        r = client.post(
            "/api/挂牌/挂-I3/隔离",
            json={"kind": "超期隔离", "reason": "催取未果"},
        )
        assert r.status_code == 200
    # 重复登记与服务守卫同口径，自检不得误报非法；现行态与事件末态仍闭合
    assert client.get("/api/链路自检").json()["一致"] is True


def test_watermark_tamper_detected(client):
    make_ticket(client, "挂-I4")
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("UPDATE watermarks SET value=999 WHERE key='在途票'")
    conn.commit()
    conn.close()
    body = client.get("/api/链路自检").json()
    assert body["一致"] is False
    assert body["水位"]["watermarks"] != body["水位"]["重放"]
