"""FastAPI server: /health endpoint and agent API."""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agent.config import DB_PATH
from agent.db import get_conn

app = FastAPI(title="pyagent", version="0.6.0")


@app.get("/health")
def health():
    """Health check. Returns status + last run info."""
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT id, provider, iterations, total_tokens, status, started_at "
            "FROM runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        conn.close()

        last_run = dict(row) if row else None
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "db_path": DB_PATH,
            "last_run": last_run,
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "error": str(e)},
        )


@app.get("/")
def root():
    return {"name": "pyagent", "version": "0.6.0", "docs": "/docs"}
