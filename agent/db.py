"""SQLite state: conversations, messages, run traces."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from agent.config import DB_PATH


def get_conn() -> sqlite3.Connection:
    parent = os.path.dirname(os.path.abspath(DB_PATH))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # WAL mode for better concurrency; busy_timeout for lock contention.
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
    except sqlite3.Error:
        pass
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conv_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conv_id) REFERENCES conversations(id)
        );
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            conv_id TEXT NOT NULL,
            provider TEXT,
            iterations INTEGER,
            total_tokens INTEGER,
            status TEXT NOT NULL,
            error TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            FOREIGN KEY (conv_id) REFERENCES conversations(id)
        );
    """)
    conn.commit()
    conn.close()


def create_conversation(conv_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO conversations (id, created_at, updated_at) VALUES (?, ?, ?)",
        (conv_id, now, now),
    )
    conn.commit()
    conn.close()


def save_message(
    conv_id: str,
    role: str,
    content: Optional[str] = None,
    tool_calls: Optional[list[Any]] = None,
    tool_call_id: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO messages (conv_id, role, content, tool_calls, tool_call_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, role, content, json.dumps(tool_calls) if tool_calls else None, tool_call_id, now),
    )
    conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
    conn.commit()
    conn.close()


def save_run(
    run_id: str,
    conv_id: str,
    provider: Optional[str],
    iterations: int,
    total_tokens: int,
    status: str,
    error: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO runs (id, conv_id, provider, iterations, total_tokens, "
        "status, error, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, conv_id, provider, iterations, total_tokens, status, error, now, now),
    )
    conn.commit()
    conn.close()


def get_conversation_messages(conv_id: str) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content, tool_calls, tool_call_id FROM messages WHERE conv_id = ? ORDER BY id",
        (conv_id,),
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        msg = {"role": row["role"]}
        if row["content"] is not None:
            msg["content"] = row["content"]
        if row["tool_calls"]:
            msg["tool_calls"] = json.loads(row["tool_calls"])
        if row["tool_call_id"]:
            msg["tool_call_id"] = row["tool_call_id"]
        result.append(msg)
    return result


def list_conversations(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, created_at, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_runs(limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, conv_id, provider, iterations, total_tokens, status, started_at "
        "FROM runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
