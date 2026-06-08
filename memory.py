"""Agent memory management using SQLite.

Supports:
- Conversation history (session memory)
- Key-value long-term memory
"""

import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional


class Memory:
    """Manages agent memory with SQLite backend."""

    def __init__(self, db_path: str = "nanoagent.db"):
        self._local = threading.local()
        self.db_path = db_path
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS long_term (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        self._conn.commit()

    # -- Conversation memory --

    def add_message(self, role: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO conversations (role, content) VALUES (?, ?)",
            (role, content),
        )
        self._conn.commit()

    def get_recent_messages(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        messages = [{"role": row["role"], "content": row["content"]} for row in rows]
        messages.reverse()
        return messages

    def clear_conversations(self) -> None:
        self._conn.execute("DELETE FROM conversations")
        self._conn.commit()

    # -- Long-term memory --

    def remember(self, key: str, value: str) -> None:
        self._conn.execute(
            """INSERT INTO long_term (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   updated_at = datetime('now')""",
            (key, value),
        )
        self._conn.commit()

    def recall(self, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM long_term WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def recall_all(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT key, value FROM long_term").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def forget(self, key: str) -> None:
        self._conn.execute("DELETE FROM long_term WHERE key = ?", (key,))
        self._conn.commit()
