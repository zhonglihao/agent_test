from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from app.core.config import get_settings


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


class Database:
    def __init__(self, db_path: Path | None = None) -> None:
        settings = get_settings()
        self.db_path = db_path or settings.db_path
        self._init_schema()

    def _init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '新对话',
                    persona_id TEXT,
                    summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, created_at);

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    scope_key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memories_scope
                    ON memories(scope_key, updated_at);
                """
            )

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = _connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_session(
        self,
        *,
        title: str = "新对话",
        persona_id: str | None = None,
    ) -> dict[str, Any]:
        session_id = str(uuid4())
        now = _utcnow()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, title, persona_id, summary, created_at, updated_at)
                VALUES (?, ?, ?, '', ?, ?)
                """,
                (session_id, title, persona_id, now, now),
            )
        return self.get_session(session_id)  # type: ignore[return-value]

    def list_sessions(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        persona_id: str | None = None,
        summary: str | None = None,
        touch: bool = True,
    ) -> dict[str, Any] | None:
        session = self.get_session(session_id)
        if not session:
            return None
        fields: list[str] = []
        values: list[Any] = []
        if title is not None:
            fields.append("title = ?")
            values.append(title)
        if persona_id is not None:
            fields.append("persona_id = ?")
            values.append(persona_id)
        if summary is not None:
            fields.append("summary = ?")
            values.append(summary)
        if touch:
            fields.append("updated_at = ?")
            values.append(_utcnow())
        if not fields:
            return session
        values.append(session_id)
        with self.connection() as conn:
            conn.execute(
                f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?",
                values,
            )
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        with self.connection() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cur.rowcount > 0

    def add_message(self, session_id: str, role: str, content: str) -> dict[str, Any]:
        message_id = str(uuid4())
        now = _utcnow()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO messages (id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (message_id, session_id, role, content, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
        return {
            "id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": now,
        }

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_messages(self, session_id: str) -> int:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return int(row["c"]) if row else 0

    def list_memories(self, scope_key: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memories
                WHERE scope_key = ?
                ORDER BY updated_at DESC
                """,
                (scope_key,),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_memory(self, scope_key: str, content: str) -> dict[str, Any]:
        memory_id = str(uuid4())
        now = _utcnow()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO memories (id, scope_key, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (memory_id, scope_key, content.strip(), now, now),
            )
        return {
            "id": memory_id,
            "scope_key": scope_key,
            "content": content.strip(),
            "created_at": now,
            "updated_at": now,
        }

    def delete_memory(self, memory_id: str) -> bool:
        with self.connection() as conn:
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cur.rowcount > 0

    def delete_memories_matching(self, scope_key: str, keyword: str) -> int:
        with self.connection() as conn:
            cur = conn.execute(
                """
                DELETE FROM memories
                WHERE scope_key = ? AND content LIKE ?
                """,
                (scope_key, f"%{keyword}%"),
            )
        return cur.rowcount
