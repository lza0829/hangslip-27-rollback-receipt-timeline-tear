from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient


def test_legacy_db_migration_backfills_event_kinds(tmp_path, monkeypatch):
    """旧库 process_events 无 kind 列：迁移补列并按语义回填，自检仍一致。"""
    db_path = tmp_path / "legacy.db"
    # 用旧版 schema（无 kind）手工造一张已推进到待取并已取衣的票
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE stores (id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT,
          rack_count INTEGER DEFAULT 2, active INTEGER DEFAULT 1);
        CREATE TABLE hang_tickets (id INTEGER PRIMARY KEY, ticket_no TEXT UNIQUE,
          store_code TEXT, pickup_code TEXT, customer_name TEXT, status TEXT,
          opened_at TEXT, due_date TEXT, closed_at TEXT, note TEXT DEFAULT '');
        CREATE TABLE ticket_items (id INTEGER PRIMARY KEY, ticket_no TEXT,
          garment TEXT, qty INTEGER, remark TEXT DEFAULT '');
        CREATE TABLE process_events (id INTEGER PRIMARY KEY, ticket_no TEXT,
          from_status TEXT, to_status TEXT, operator TEXT, occurred_at TEXT,
          note TEXT DEFAULT '');
        CREATE TABLE pickups (id INTEGER PRIMARY KEY, ticket_no TEXT UNIQUE,
          pickup_code TEXT, picked_at TEXT, operator TEXT);
        CREATE TABLE quarantines (id INTEGER PRIMARY KEY, ticket_no TEXT, kind TEXT,
          reason TEXT, created_at TEXT, resolved INTEGER DEFAULT 0);
        CREATE TABLE day_gates (day TEXT PRIMARY KEY, sealed INTEGER DEFAULT 0,
          sealed_at TEXT, note TEXT DEFAULT '');
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE watermarks (key TEXT PRIMARY KEY, value INTEGER, updated_at TEXT);
        INSERT INTO stores(code,name,active) VALUES ('店-河西','河西干洗',1);
        INSERT INTO hang_tickets VALUES (1,'挂-旧1','店-河西','暗码旧','旧客','已取',
          '2026-11-01 09:00:00','2026-11-02', '2026-11-03 10:00:00','');
        INSERT INTO ticket_items VALUES (1,'挂-旧1','衬衣',1,'');
        INSERT INTO process_events VALUES
          (1,'挂-旧1',NULL,'已收','店员','2026-11-01 09:00:00','开票'),
          (2,'挂-旧1','已收','待取','店员','2026-11-01 09:10:00','推进'),
          (3,'挂-旧1','待取','已取','柜员','2026-11-03 10:00:00','取衣');
        INSERT INTO pickups VALUES (1,'挂-旧1','暗码旧','2026-11-03 10:00:00','柜员');
        """
    )
    conn.commit()
    conn.close()

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
    import app.routers.tickets as tr
    importlib.reload(tr)
    import app.main as main
    importlib.reload(main)

    seed.seed_if_empty()  # 内部 init_db 触发迁移；门店已存在故跳过种子

    cols = {r[1] for r in sqlite3.connect(db_path).execute("PRAGMA table_info(process_events)")}
    assert "kind" in cols

    with TestClient(main.app) as client:
        evs = client.get("/api/挂牌/挂-旧1").json()["events"]
        kinds = [e["kind"] for e in evs]
        assert kinds == ["收衣", "推进", "取衣"]
        # 旧票终态为已取，倒回硬拒绝
        r = client.post("/api/挂牌/挂-旧1/倒回", json={"operator": "工序员"})
        assert r.status_code == 409
        # 迁移后新倒回能力对在途票可用
        body = {
            "ticket_no": "挂-新1", "store_code": "店-河西", "pickup_code": "码新",
            "customer_name": "新客", "due_date": "2026-12-31",
            "items": [{"garment": "裤", "qty": 1}],
        }
        client.post("/api/挂牌", json=body)
        client.post("/api/挂牌/挂-新1/推进", json={"to_status": "水洗"})
        assert client.post("/api/挂牌/挂-新1/倒回", json={}).status_code == 200
        assert client.get("/api/链路自检").json()["一致"] is True
