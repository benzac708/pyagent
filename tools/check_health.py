"""Check the health of an HTTP endpoint (read-only)."""

import urllib.request

from pydantic import BaseModel


class CheckHealthInput(BaseModel):
    url: str


def check_health(url: str) -> str:
    """Return health status for an HTTP endpoint. Read-only, no side effects."""
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            body = r.read().decode()
            return f"url={url} status=healthy http={r.status} body={body[:200]}"
    except Exception as e:
        return f"url={url} status=unhealthy error={e}"
