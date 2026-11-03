"""FastAPI server: /health endpoint and agent API."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.config import DB_PATH
from agent.db import get_conn, init_db
from agent.loop import run as run_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="pyagent", version="0.6.0", lifespan=lifespan)


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


class RunRequest(BaseModel):
    prompt: str
    verbose: bool = False


@app.post("/run")
def run_endpoint(req: RunRequest):
    """Invoke the agent with a prompt and return the result."""
    try:
        result = run_agent(req.prompt, verbose=req.verbose, quiet=True)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    return {"name": "pyagent", "version": "0.6.0", "docs": "/docs"}
