from __future__ import annotations

import threading

from conftest import make_ticket


def _events(client, no):
    return client.get(f"/api/挂牌/{no}").json()["events"]


def _status(client, no):
    return client.get(f"/api/挂牌/{no}").json()["status"]


def _advance(client, no, to):
    r = client.post(f"/api/挂牌/{no}/推进", json={"to_status": to, "operator": "工序员"})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 倒回基本规则 ----------

def test_rollback_one_step_to_adjacent_previous(client):
    make_ticket(client, "挂-T1")
    _advance(client, "挂-T1", "水洗")
    _advance(client, "挂-T1", "烘干")

    r = client.post("/api/挂牌/挂-T1/倒回", json={"operator": "工序员", "note": "推错档"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "水洗"

    kinds = [(e["kind"], e["from_status"], e["to_status"]) for e in _events(client, "挂-T1")]
    assert kinds == [
        ("收衣", None, "已收"),
        ("推进", "已收", "水洗"),
        ("推进", "水洗", "烘干"),
        ("倒回", "烘干", "水洗"),
    ]


def test_rollback_is_single_step_only_even_after_forward_skip(client):
    # 前进允许跳步（已收→熨烫），倒回仍只能回相邻上一档（熨烫→烘干）
    make_ticket(client, "挂-T2")
    _advance(client, "挂-T2", "熨烫")

    r = client.post("/api/挂牌/挂-T2/倒回", json={"operator": "工序员"})
    assert r.status_code == 200
    assert r.json()["status"] == "烘干"


def test_rollback_from_ready_leaves_ready_page_and_can_re_advance(client):
    make_ticket(client, "挂-T3")
    _advance(client, "挂-T3", "待取")
    # 待取页可见
    ready = client.get("/api/挂牌", params={"status": "待取"}).json()
    assert any(t["ticket_no"] == "挂-T3" for t in ready)

    r = client.post("/api/挂牌/挂-T3/倒回", json={"operator": "工序员"})
    assert r.status_code == 200
    assert r.json()["status"] == "熨烫"

    # 倒回后必须从待取页消失（不能“已取票被倒回待取”式的可见性分裂）
    ready = client.get("/api/挂牌", params={"status": "待取"}).json()
    assert all(t["ticket_no"] != "挂-T3" for t in ready)

    # 再推进回待取，重新可见
    _advance(client, "挂-T3", "待取")
    ready = client.get("/api/挂牌", params={"status": "待取"}).json()
    assert any(t["ticket_no"] == "挂-T3" for t in ready)


def test_double_rollback_walks_chain_back(client):
    make_ticket(client, "挂-T4")
    _advance(client, "挂-T4", "熨烫")
    client.post("/api/挂牌/挂-T4/倒回", json={"operator": "工序员"})
    r = client.post("/api/挂牌/挂-T4/倒回", json={"operator": "工序员"})
    assert r.status_code == 200
    assert r.json()["status"] == "水洗"


# ---------- 硬边界 ----------

def test_rollback_at_first_step_rejected(client):
    make_ticket(client, "挂-T5")  # 已收即首档
    r = client.post("/api/挂牌/挂-T5/倒回", json={"operator": "工序员"})
    assert r.status_code == 409
    assert "首档" in r.json()["detail"]


def test_rollback_after_pickup_is_hard_rejected(client):
    make_ticket(client, "挂-T6", code="暗码甲")
    _advance(client, "挂-T6", "待取")
    r = client.post("/api/挂牌/挂-T6/取衣", json={"pickup_code": "暗码甲", "operator": "柜员"})
    assert r.status_code == 200

    r = client.post("/api/挂牌/挂-T6/倒回", json={"operator": "工序员"})
    assert r.status_code == 409
    assert "终态" in r.json()["detail"]
    # 现行态没有被拨回
    assert _status(client, "挂-T6") == "已取"
    # 已取票不出现在待取页
    ready = client.get("/api/挂牌", params={"status": "待取"}).json()
    assert all(t["ticket_no"] != "挂-T6" for t in ready)


def test_rollback_quarantined_ticket_is_hard_rejected(client):
    make_ticket(client, "挂-T7")
    _advance(client, "挂-T7", "待取")
    r = client.post(
        "/api/挂牌/挂-T7/隔离",
        json={"kind": "超期隔离", "reason": "逾承诺日", "operator": "店长"},
    )
    assert r.status_code == 200

    r = client.post("/api/挂牌/挂-T7/倒回", json={"operator": "工序员"})
    assert r.status_code == 409
    assert _status(client, "挂-T7") == "超期隔离"


def test_rollback_unknown_ticket_404(client):
    r = client.post("/api/挂牌/挂-不存在/倒回", json={"operator": "工序员"})
    assert r.status_code == 404


def test_rollback_blocked_when_day_sealed(client):
    make_ticket(client, "挂-T8")
    _advance(client, "挂-T8", "水洗")
    assert client.post("/api/日闸/结案", json={"note": "结案"}).status_code == 200
    r = client.post("/api/挂牌/挂-T8/倒回", json={"operator": "工序员"})
    assert r.status_code == 409


# ---------- 事件链重放与联动 ----------

def test_chain_self_check_consistent_through_rollback(client):
    make_ticket(client, "挂-T9")
    _advance(client, "挂-T9", "烘干")
    client.post("/api/挂牌/挂-T9/倒回", json={"operator": "工序员"})
    _advance(client, "挂-T9", "熨烫")
    client.post("/api/挂牌/挂-T9/倒回", json={"operator": "工序员"})

    r = client.get("/api/链路自检")
    assert r.status_code == 200
    body = r.json()
    assert body["一致"] is True
    assert body["分裂票"] == []
    assert body["非法事件"] == []


def test_replay_matches_current_after_mixed_chain(client):
    make_ticket(client, "挂-T10")
    for to in ("水洗", "烘干", "熨烫", "待取"):
        _advance(client, "挂-T10", to)
    client.post("/api/挂牌/挂-T10/倒回", json={"operator": "工序员"})  # →熨烫
    assert _status(client, "挂-T10") == "熨烫"
    # 重放末事件终点即现行态
    assert _events(client, "挂-T10")[-1]["to_status"] == "熨烫"


def test_watermark_and_dashboard_distribution_follow_rollback(client):
    make_ticket(client, "挂-T11")
    _advance(client, "挂-T11", "待取")
    before = client.get("/api/总览").json()
    assert before["待取"] >= 1

    client.post("/api/挂牌/挂-T11/倒回", json={"operator": "工序员"})  # →熨烫
    after = client.get("/api/总览").json()

    # 总览分布按现行态联动
    assert after["待取"] == before["待取"] - 1
    assert after["熨烫"] == before["熨烫"] + 1
    # 在途水位：倒回前后都在途，数值不变但必须仍等于重放值
    check = client.get("/api/链路自检").json()
    assert check["水位"]["watermarks"] == check["水位"]["重放"]


def test_pickup_lowers_watermark_and_self_check_stays_green(client):
    make_ticket(client, "挂-T12", code="暗码乙")
    _advance(client, "挂-T12", "待取")
    d0 = client.get("/api/总览").json()
    client.post("/api/挂牌/挂-T12/取衣", json={"pickup_code": "暗码乙", "operator": "柜员"})
    d1 = client.get("/api/总览").json()
    assert d1["在途水位"] == d0["在途水位"] - 1
    assert client.get("/api/链路自检").json()["一致"] is True


# ---------- 并发：倒回 × 取衣不得双终态 ----------

def test_concurrent_rollback_and_pickup_single_terminal_outcome(client):
    make_ticket(client, "挂-T13", code="暗码并发")
    _advance(client, "挂-T13", "待取")

    outcomes = []

    def do_rollback():
        r = client.post("/api/挂牌/挂-T13/倒回", json={"operator": "工序员"})
        outcomes.append(("倒回", r.status_code))

    def do_pickup():
        r = client.post(
            "/api/挂牌/挂-T13/取衣",
            json={"pickup_code": "暗码并发", "operator": "柜员"},
        )
        outcomes.append(("取衣", r.status_code))

    t1 = threading.Thread(target=do_rollback)
    t2 = threading.Thread(target=do_pickup)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    status = _status(client, "挂-T13")
    # 恰好一个终态结果：要么已取（取衣赢），要么熨烫（倒回赢，取衣因非待取被拒）
    assert status in ("已取", "熨烫")
    codes = {o[0] for o in outcomes if o[1] == 200}
    assert codes in ({"取衣"}, {"倒回"})
    if status == "已取":
        assert "倒回" not in codes
    else:
        # 倒回成功后取衣必须 409，且票未被核销
        assert ("取衣", 409) in outcomes
        assert not any(
            p["ticket_no"] == "挂-T13"
            for p in [client.get("/api/挂牌/挂-T13").json()]
            if p["status"] == "已取"
        )
    # 无论谁赢，事件链与现行态仍闭合
    assert client.get("/api/链路自检").json()["一致"] is True


def test_concurrent_two_rollbacks_serialize_to_two_steps_back(client):
    make_ticket(client, "挂-T14")
    _advance(client, "挂-T14", "熨烫")  # 已收→水洗→烘干→熨烫
    results = []

    def roll():
        r = client.post("/api/挂牌/挂-T14/倒回", json={"operator": "工序员"})
        results.append(r.status_code)

    threads = [threading.Thread(target=roll) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # BEGIN IMMEDIATE 串行：两次倒回各自成功，合计退回两档到水洗，无报错无脏写
    assert sorted(results) == [200, 200]
    assert _status(client, "挂-T14") == "水洗"
    assert client.get("/api/链路自检").json()["一致"] is True
