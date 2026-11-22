from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """每个用例一个全新临时库，重新加载 app，杜绝跨用例状态泄漏。"""
    db_path = tmp_path / "test-hangslip.db"
    monkeypatch.setenv("HANGSLIP_DB", str(db_path))

    import app.config as config
    importlib.reload(config)
    import app.db as db
    importlib.reload(db)
    import app.services.timeline as timeline
    importlib.reload(timeline)
    import app.services.gate as gate
    importlib.reload(gate)
    import app.services.tickets as tickets
    importlib.reload(tickets)
    import app.seed as seed
    importlib.reload(seed)
    import app.routers.dashboard as dashboard
    importlib.reload(dashboard)
    import app.routers.tickets as tickets_router
    importlib.reload(tickets_router)
    import app.routers.gates as gates_router
    importlib.reload(gates_router)
    import app.main as main
    importlib.reload(main)

    seed.seed_if_empty()
    with TestClient(main.app) as c:
        yield c


def make_ticket(client: TestClient, ticket_no: str, *, store: str = "店-河西",
                code: str = "暗码测试", customer: str = "测试客") -> dict:
    body = {
        "ticket_no": ticket_no,
        "store_code": store,
        "pickup_code": code,
        "customer_name": customer,
        "due_date": "2026-12-31",
        "items": [{"garment": "衬衣", "qty": 1}],
        "operator": "测试员",
    }
    r = client.post("/api/挂牌", json=body)
    assert r.status_code == 200, r.text
    return r.json()
