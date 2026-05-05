"""SQLite session storage with WAL-mode concurrency, query, and index support.

Drop-in replacement for LocalSessionStore with the same public API,
plus search/query/list capabilities suitable for multi-instance deployments.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from .models import AIMessage, RuntimeEvent, ToolCall


class SQLiteSessionStore:
    """SQLite-backed session store with WAL-mode concurrent reads.

    Supports:
    - Multiple reader processes (WAL mode)
    - Indexed queries by session, time range, role
    - Message content search
    - Session metadata (name, pin, created time)
    - Same API as LocalSessionStore for drop-in replacement
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._db_path = self.root / "sessions.db"
        self._local = threading.local()
        self._init_db()

    # ── Connection management (thread-safe) ──────────────────────────

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                name TEXT,
                first_message TEXT,
                pinned INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                seq INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('system','user','assistant','tool')),
                content TEXT DEFAULT '',
                name TEXT,
                tool_call_id TEXT,
                tool_calls_json TEXT,
                created_at REAL NOT NULL DEFAULT (unixepoch('subsec')),
                UNIQUE(session_id, seq)
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                seq INTEGER NOT NULL,
                type TEXT NOT NULL,
                message TEXT DEFAULT '',
                data_json TEXT DEFAULT '{}',
                created_at REAL NOT NULL DEFAULT (unixepoch('subsec')),
                UNIQUE(session_id, seq)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session_seq
                ON messages(session_id, seq);
            CREATE INDEX IF NOT EXISTS idx_messages_session_role
                ON messages(session_id, role);
            CREATE INDEX IF NOT EXISTS idx_messages_created
                ON messages(created_at);
            CREATE INDEX IF NOT EXISTS idx_events_session_seq
                ON events(session_id, seq);
            CREATE INDEX IF NOT EXISTS idx_sessions_pinned_created
                ON sessions(pinned, created_at);
            CREATE INDEX IF NOT EXISTS idx_sessions_created
                ON sessions(created_at);
        """)
        conn.commit()
        conn.close()

    # ── Public API (same as LocalSessionStore) ────────────────────────

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO sessions (id, created_at) VALUES (?, ?)",
            (session_id, time.time()),
        )
        self._conn.commit()
        (self.root / session_id / "artifacts").mkdir(parents=True, exist_ok=True)
        return session_id

    def session_exists(self, session_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return row is not None

    def artifact_dir(self, session_id: str) -> Path:
        path = self.root / session_id / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def append_message(self, session_id: str, message: AIMessage) -> None:
        seq = self._next_seq("messages", session_id)
        tool_calls_json = None
        if message.tool_calls:
            tool_calls_json = json.dumps(
                [tc.model_dump(mode="json") for tc in message.tool_calls],
                ensure_ascii=False,
            )
        self._conn.execute(
            """INSERT OR IGNORE INTO messages
               (session_id, seq, role, content, name, tool_call_id, tool_calls_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, seq, message.role, message.content or "",
             message.name, message.tool_call_id, tool_calls_json),
        )
        self._conn.commit()

    def load_messages(self, session_id: str) -> list[AIMessage]:
        rows = self._conn.execute(
            "SELECT role, content, name, tool_call_id, tool_calls_json "
            "FROM messages WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def append_event(self, session_id: str, event: RuntimeEvent) -> None:
        seq = self._next_seq("events", session_id)
        self._conn.execute(
            """INSERT OR IGNORE INTO events
               (session_id, seq, type, message, data_json)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, seq, event.type, event.message,
             json.dumps(event.data, ensure_ascii=False)),
        )
        self._conn.commit()

    def load_events(self, session_id: str) -> list[RuntimeEvent]:
        rows = self._conn.execute(
            "SELECT type, message, data_json FROM events "
            "WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [
            RuntimeEvent(type=r["type"], message=r["message"],
                         data=json.loads(r["data_json"]))
            for r in rows
        ]

    # ── Extended API — query, search, list ───────────────────────────

    def list_sessions(self, pinned_first: bool = True,
                      limit: int = 50, offset: int = 0) -> list[dict]:
        """List sessions with metadata, ordered by pinned+created."""
        _ORDER_MAP = {
            True: "pinned DESC, created_at DESC",
            False: "created_at DESC",
        }
        order = _ORDER_MAP.get(pinned_first, "created_at DESC")
        rows = self._conn.execute(
            f"SELECT id, created_at, name, first_message, pinned "
            f"FROM sessions ORDER BY {order} LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [
            {
                "id": r["id"], "created": r["created_at"],
                "name": r["name"] or r["id"][:8] + "...",
                "first_message": r["first_message"] or "",
                "pinned": bool(r["pinned"]),
            }
            for r in rows
        ]

    def set_session_meta(self, session_id: str, *,
                         name: Optional[str] = None,
                         pinned: Optional[bool] = None,
                         first_message: Optional[str] = None) -> bool:
        """Update session metadata. Returns True if session exists."""
        fields = []
        values = []
        if name is not None:
            fields.append("name = ?"); values.append(name)
        if pinned is not None:
            fields.append("pinned = ?"); values.append(int(pinned))
        if first_message is not None:
            fields.append("first_message = ?"); values.append(first_message)
        if not fields:
            return self.session_exists(session_id)
        values.append(session_id)
        cur = self._conn.execute(
            f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?", values
        )
        self._conn.commit()
        return cur.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages/events. Cascades via FK."""
        cur = self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._conn.commit()
        # Clean up file artifacts
        import shutil
        session_dir = self.root / session_id
        if session_dir.exists():
            shutil.rmtree(str(session_dir), ignore_errors=True)
        return cur.rowcount > 0

    def search_messages(self, query: str, session_id: Optional[str] = None,
                        limit: int = 20) -> list[dict]:
        """Full-text search across message content using LIKE.

        For production, consider FTS5 extension for better performance.
        """
        like_pattern = f"%{query}%"
        if session_id:
            rows = self._conn.execute(
                "SELECT m.session_id, m.role, m.content, m.created_at, s.name "
                "FROM messages m JOIN sessions s ON m.session_id = s.id "
                "WHERE m.session_id = ? AND m.content LIKE ? "
                "ORDER BY m.seq LIMIT ?",
                (session_id, like_pattern, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT m.session_id, m.role, m.content, m.created_at, s.name "
                "FROM messages m JOIN sessions s ON m.session_id = s.id "
                "WHERE m.content LIKE ? "
                "ORDER BY m.created_at DESC LIMIT ?",
                (like_pattern, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_session_stats(self) -> dict:
        """Return aggregate stats: total sessions, messages, events."""
        sessions = self._conn.execute(
            "SELECT COUNT(*) as n FROM sessions"
        ).fetchone()["n"]
        messages = self._conn.execute(
            "SELECT COUNT(*) as n FROM messages"
        ).fetchone()["n"]
        events = self._conn.execute(
            "SELECT COUNT(*) as n FROM events"
        ).fetchone()["n"]
        return {"sessions": sessions, "messages": messages, "events": events}

    def message_count(self, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) as n FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row["n"] if row else 0

    # ── Vacuum (maintenance) ─────────────────────────────────────────

    def vacuum(self) -> None:
        """Reclaim disk space. Call periodically or after bulk deletes."""
        self._conn.execute("PRAGMA optimize")
        self._conn.commit()

    # ── Helpers ──────────────────────────────────────────────────────

    def _next_seq(self, table: str, session_id: str) -> int:
        row = self._conn.execute(
            f"SELECT COALESCE(MAX(seq), -1) + 1 as nxt FROM {table} "
            f"WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row["nxt"]

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> AIMessage:
        tool_calls = None
        if row["tool_calls_json"]:
            try:
                raw = json.loads(row["tool_calls_json"])
                tool_calls = [ToolCall(**tc) for tc in raw]
            except (json.JSONDecodeError, TypeError):
                pass
        return AIMessage(
            role=row["role"],
            content=row["content"] or "",
            name=row["name"],
            tool_call_id=row["tool_call_id"],
            tool_calls=tool_calls,
        )
