"""Read recent run records from the agent's own SQLite database (read-only)."""

import os
import sqlite3

from pydantic import BaseModel


class ListRunsInput(BaseModel):
    limit: int = 5


def list_runs(limit: int = 5) -> str:
    """Return the most recent agent runs as a formatted string. Read-only."""
    try:
        db_path = os.getenv("DB_PATH", "agent.db")
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT id, conv_id, provider, iterations, total_tokens, status, started_at "
            "FROM runs ORDER BY started_at DESC LIMIT ?",
            (max(1, min(limit, 50)),),
        ).fetchall()
        conn.close()
        if not rows:
            return "No runs recorded yet."
        lines = []
        for r in rows:
            lines.append(
                f"id={r[0]} conv={r[1]} provider={r[2]} iters={r[3]} " f"tokens={r[4]} status={r[5]} started={r[6]}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"
