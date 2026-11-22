from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS stores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  rack_count INTEGER NOT NULL DEFAULT 2,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS hang_tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_no TEXT NOT NULL UNIQUE,
  store_code TEXT NOT NULL,
  pickup_code TEXT NOT NULL,
  customer_name TEXT NOT NULL,
  status TEXT NOT NULL,
  opened_at TEXT NOT NULL,
  due_date TEXT NOT NULL,
  closed_at TEXT,
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS ticket_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_no TEXT NOT NULL,
  garment TEXT NOT NULL,
  qty INTEGER NOT NULL,
  remark TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS process_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_no TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT '推进',
  from_status TEXT,
  to_status TEXT NOT NULL,
  operator TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS pickups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_no TEXT NOT NULL UNIQUE,
  pickup_code TEXT NOT NULL,
  picked_at TEXT NOT NULL,
  operator TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_no TEXT NOT NULL,
  kind TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  resolved INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS day_gates (
  day TEXT PRIMARY KEY,
  sealed INTEGER NOT NULL DEFAULT 0,
  sealed_at TEXT,
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watermarks (
  key TEXT PRIMARY KEY,
  value INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);
"""

STATUSES = ("已收", "水洗", "烘干", "熨烫", "待取", "已取", "超期隔离", "丢失隔离")
# 工序链（线性相邻序），倒回只允许沿此链回到相邻上一档
PROCESS_CHAIN = ("已收", "水洗", "烘干", "熨烫", "待取")
FORWARD = {
    "已收": ("水洗", "烘干", "熨烫", "待取"),
    "水洗": ("烘干", "熨烫", "待取"),
    "烘干": ("熨烫", "待取"),
    "熨烫": ("待取",),
    "待取": (),
}
# 相邻上一档；不在链上的终态（已取/隔离）没有前驱，倒回硬拒绝
PREV = {cur: PROCESS_CHAIN[i - 1] for i, cur in enumerate(PROCESS_CHAIN) if i > 0}
# 事件链只追加的事件种类
EVENT_KINDS = ("收衣", "推进", "倒回", "取衣", "隔离")
# 倒回/任何工序变动的硬边界：已取与隔离票的现行态不得拨回
TERMINAL = ("已取", "超期隔离", "丢失隔离")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def transaction():
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        # 轻量迁移：旧库 process_events 无 kind 列时补齐并按语义回填
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(process_events)")}
        if "kind" not in cols:
            conn.execute(
                "ALTER TABLE process_events ADD COLUMN kind TEXT NOT NULL DEFAULT '推进'"
            )
            conn.execute(
                """UPDATE process_events SET kind='取衣'
                   WHERE to_status='已取' AND COALESCE(from_status,'')='待取'"""
            )
            conn.execute(
                "UPDATE process_events SET kind='隔离' WHERE to_status IN ('超期隔离','丢失隔离')"
            )
            conn.execute(
                "UPDATE process_events SET kind='收衣' WHERE from_status IS NULL"
            )
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)
