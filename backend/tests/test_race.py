from __future__ import annotations

import threading

from conftest import make_ticket


def test_rollback_pickup_race_repeated_no_double_terminal(client):
    """20 轮倒回×取衣竞争，每一轮都只能有一个终态结果，自检始终闭合。"""
    for i in range(20):
        no = f"挂-R{i}"
        make_ticket(client, no, code=f"码{i}")
        client.post(f"/api/挂牌/{no}/推进", json={"to_status": "待取"})
        outcomes = []

        def roll():
            r = client.post(f"/api/挂牌/{no}/倒回", json={"operator": "工序员"})
            outcomes.append(("倒回", r.status_code))

        def pick():
            r = client.post(
                f"/api/挂牌/{no}/取衣", json={"pickup_code": f"码{i}", "operator": "柜员"}
            )
            outcomes.append(("取衣", r.status_code))

        t1, t2 = threading.Thread(target=roll), threading.Thread(target=pick)
        t1.start(); t2.start(); t1.join(); t2.join()

        status = client.get(f"/api/挂牌/{no}").json()["status"]
        ok = {o[0] for o in outcomes if o[1] == 200}
        assert len(ok) == 1, f"{no} 出现双成功: {outcomes}"
        if "取衣" in ok:
            assert status == "已取"
        else:
            assert status == "熨烫"
            assert ("取衣", 409) in outcomes
        assert client.get("/api/链路自检").json()["一致"] is True
