"""Optional deployment-only global POST budget, shared by both APIs via SQLite.

Counts accepted *attempts*, including failures and local tools; not a currency limit.
Authentication is enforced by Caddy. No provider credentials or photos enter this DB.
"""
import asyncio
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def charge(path: str, limit: int, day: str) -> bool:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=5)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS daily_budget(day TEXT PRIMARY KEY, used INTEGER NOT NULL)")
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO daily_budget VALUES (?, 0)", (day,))
        changed = db.execute("UPDATE daily_budget SET used=used+1 WHERE day=? AND used<?", (day, limit)).rowcount
        db.commit()
        return changed == 1


class DemoGuard:
    def __init__(self, app, *, path=None, limit=None):
        self.app = app
        self.path = path or os.environ.get("DEMO_BUDGET_DB", "/limits/budget.sqlite3")
        self.limit = int(limit if limit is not None else os.environ.get("DEMO_DAILY_POST_LIMIT", "60"))
        if self.limit < 1:
            raise ValueError("Demo request limit must be positive")

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        exempt = path.startswith("/api/auth/") or path in {"/api/assets", "/api/media/upload"} or path.endswith(("/selection", "/selection/prepare"))
        if scope["type"] == "http" and scope.get("method") == "POST" and not exempt:
            today = datetime.now(timezone.utc).date().isoformat()
            try:
                allowed = await asyncio.to_thread(charge, self.path, self.limit, today)
            except (sqlite3.Error, OSError):
                allowed = False  # budget storage failure must not silently permit paid calls
            if not allowed:
                body = json.dumps({"message": "演示版今日操作次数已用完，请联系演示者。", "detail": "Demo daily request budget exhausted"}, ensure_ascii=False).encode()
                await send({"type": "http.response.start", "status": 429, "headers": [(b"content-type", b"application/json; charset=utf-8"), (b"cache-control", b"no-store")]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
