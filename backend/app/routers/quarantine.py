from __future__ import annotations

from fastapi import APIRouter

from app.db import connect

router = APIRouter(tags=["隔离"])


@router.get("/隔离")
def list_quarantine():
    conn = connect()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM quarantines ORDER BY id DESC"
            ).fetchall()
        ]
    finally:
        conn.close()
