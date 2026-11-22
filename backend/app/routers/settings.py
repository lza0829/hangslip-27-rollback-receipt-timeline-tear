from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import connect

router = APIRouter(tags=["设置"])


class SettingIn(BaseModel):
    key: str
    value: str


@router.get("/设置")
def list_settings():
    conn = connect()
    try:
        return {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings").fetchall()}
    finally:
        conn.close()


@router.put("/设置")
def put_setting(body: SettingIn):
    conn = connect()
    try:
        conn.execute(
            """INSERT INTO settings(key, value) VALUES (?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (body.key.strip(), body.value.strip()),
        )
        conn.commit()
        return {body.key.strip(): body.value.strip()}
    finally:
        conn.close()
