"""FastAPI server: /health endpoint and agent API."""

import asyncio
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.config import DB_PATH
from agent.db import get_conn, init_db, list_conversations, list_runs
from agent.loop import run as run_agent

# --- Simple in-memory rate limiter (per client IP) ---
_RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "10"))
_rate_buckets: dict[str, deque[Any]] = defaultdict(deque)


def _check_rate_limit(client_ip: str) -> None:
    now = time.time()
    bucket = _rate_buckets[client_ip]
    while bucket and bucket[0] < now - 60:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


def _check_auth(request: Request) -> None:
    expected = os.getenv("PYAGENT_API_KEY", "")
    if not expected:
        return  # auth disabled when no key configured
    provided = request.headers.get("x-api-key", "")
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    init_db()
    yield


app = FastAPI(title="pyagent", version="0.7.0", lifespan=lifespan)


@app.get("/health")
def health() -> Any:
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
async def run_endpoint(req: RunRequest, request: Request) -> dict[str, Any]:
    """Invoke the agent with a prompt and return the result."""
    _check_auth(request)
    _check_rate_limit(request.client.host if request.client else "unknown")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: run_agent(req.prompt, verbose=req.verbose, quiet=True))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/runs")
def runs_endpoint(limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    return list_runs(limit=limit, offset=offset)


@app.get("/conversations")
def conversations_endpoint(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    return list_conversations(limit=limit, offset=offset)


@app.get("/")
def root() -> dict[str, Any]:
    return {"name": "pyagent", "version": "0.7.0", "docs": "/docs"}
