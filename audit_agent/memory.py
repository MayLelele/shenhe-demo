# -*- coding: utf-8 -*-
"""短期会话记忆 + SQLite 长期记忆。"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class MemoryStore:
    """长期记忆：按 session_id 存关键事实与摘要，便于多轮延续。"""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def append(self, session_id: str, kind: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO memories (session_id, kind, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, kind, content, time.time()),
        )
        self._conn.commit()

    def recent(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            """
            SELECT kind, content, created_at FROM memories
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        rows.reverse()
        return rows

    def format_context(self, session_id: str, limit: int = 12) -> str:
        parts = []
        for row in self.recent(session_id, limit=limit):
            parts.append(f"[{row['kind']}] {row['content']}")
        if not parts:
            return "（尚无长期记忆记录）"
        return "\n".join(parts)

    def close(self) -> None:
        self._conn.close()


def dumps_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
